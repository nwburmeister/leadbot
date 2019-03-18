from flask_wtf import FlaskForm, Form
from wtforms import TextAreaField
from wtforms import StringField, PasswordField, SubmitField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_login import current_user
from app.models import Users
import phonenumbers


class RegistrationForm(FlaskForm):
    """
    A class to create a web-form for registering for the site.
    """
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=20)])
    company_name = StringField('Company Name', validators=[DataRequired(), Length(min=2, max=20)])
    company_email = StringField('Company Email', validators=[DataRequired(), Email()])
    company_phone = StringField('Company Phone', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Register')

    def validate_company_email(self, company_email):
        email = Users.query.filter_by(company_email=company_email.data).first()
        if email:
            raise ValidationError("email already registered")

    def validate_username(self, username):
        user = Users.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("username taken")


    def validate_phone(self, field):
        if len(field.data) > 16:
            raise ValidationError('Invalid phone number.')
        try:
            input_number = phonenumbers.parse(field.data)
            if not (phonenumbers.is_valid_number(input_number)):
                raise ValidationError('Invalid phone number.')
        except:
            input_number = phonenumbers.parse("+1" + field.data)
            if not (phonenumbers.is_valid_number(input_number)):
                raise ValidationError('Invalid phone number.')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class UpdateAccountForm(FlaskForm):
    """
    A class to create a web-form for registering for the site.
    """
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])

    submit = SubmitField('Update')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = Users.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError("username taken")

    def validate_email(self, email):
        if email.data != current_user.email:
            email = Users.query.filter_by(username=email.data).first()
            if email:
                raise ValidationError("email already registered")


class PostForm(Form):
    subject = TextAreaField(render_kw={'maxlength': 100})
    body = TextAreaField(default=" ")
    recipient = TextAreaField(render_kw={'maxlength': 20})


class RemoveRecord(FlaskForm):
    submit = SubmitField('Remove Record')


class RedditAccountConfiguration(FlaskForm):
    client_id = StringField('Account Id', validators=[DataRequired()])
    client_secret = StringField('Secret Key', validators=[DataRequired()])
    reddit_account_username = StringField('Username', validators=[DataRequired()])
    reddit_password = StringField('Password', validators=[DataRequired()])
    submit = SubmitField('Update Reddit Account Info')


class AutoMessengerSettings(FlaskForm):
    number_of_messages = IntegerField('Number of Messages to Send (int)', validators=[DataRequired()])
    sleep_time = IntegerField('Time Between Messages (seconds)', validators=[DataRequired()])
    submit = SubmitField('Begin Automatic Messaging')
