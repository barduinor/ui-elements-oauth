# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from distutils.log import error
from apps.config import Config
from flask import render_template, redirect, request, url_for
from flask_login import (
    current_user,
    login_user,
    logout_user
)

from boxsdk import OAuth2
from boxsdk import Client

from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Access_Token, Csrf_token, Users

from apps.authentication.util import verify_pass

# @blueprint.route('/')
# def route_default():
#     return redirect(url_for('authentication_blueprint.login'))

@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login_box'))

# Login & Registration

@blueprint.route('/login-box', methods=['GET', 'POST'])
def login_box():
    oauth = OAuth2(
        client_id=Config.CLIENT_ID,
        client_secret=Config.CLIENT_SECRET,
    )
    auth_url, csrf_token = oauth.get_authorization_url(Config.REDIRECT_URI)
    db.session.add(Csrf_token(csrf_token))
    db.session.commit()

    return render_template('accounts/login-box.html', auth_url=auth_url, csrf_token=csrf_token)

@blueprint.route('/oauth/callback')
def oauth_callback():
    print(request.args)
    code=request.args.get('code')
    state=request.args.get('state')
    error=request.args.get('error')
    error_description=request.args.get('error_description')

    if state:
        csrf_token = Csrf_token.query.filter_by(token=state).first()
        if csrf_token:
            db.session.delete(csrf_token)
            db.session.commit()
        else:
            error = 'Invalid state'
            error_description = 'CSRF token is invalid'

    if error == 'access_denied':
        return render_template('accounts/login-box.html', msg='You denied access to this application')
    elif error:
        return render_template('accounts/login-box.html', msg=error_description)

    oauth = OAuth2(
        client_id=Config.CLIENT_ID,
        client_secret=Config.CLIENT_SECRET,
    )
    access_token, refresh_token = oauth.authenticate(code)

    client = Client(oauth)

    user_info = client.user().get()
    # avatar = client.user(user_id=user_info['id']).get_avatar()

    print('user_info:')
    print('id:', user_info['id'])
    print('name:', user_info['name'])
    print('login:', user_info['login'])
    print('avatar_url:', user_info['avatar_url'])

    # Locate user
    user = Users.query.filter_by(email=user_info['login']).first()

    #New user?
    if user is None:
        #Update info
        user = Users(username=user_info['name'], email=user_info['login'], password='',avatar_url=user_info['avatar_url'])

        db.session.add(user)
        db.session.commit()
        user = Users.query.filter_by(email=user_info['login']).first()

    # Check the User exists
    if user:
        login_user(user)
    
    db.session.add(Access_Token(user_id=user.id, access_token=access_token, refresh_token=refresh_token))
    db.session.commit()

    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        username = request.form['username']
        password = request.form['password']

        # Locate user
        user = Users.query.filter_by(username=username).first()

        # Check the password
        if user and verify_pass(password, user.password):

            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
