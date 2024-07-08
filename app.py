from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import InputRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
import re
import requests

app = Flask(__name__)

app.secret_key = 'abc@123'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'AZsx@1209'
app.config['MYSQL_DB'] = 'mutualfunds'

mysql = MySQL(app)

mf_list = []

def isloggedin():
    return 'name' in session


api_url = "https://api.mfapi.in/mf/"


class signin_form(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Signin')


class login_form(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=15)])
    submit = SubmitField('Login')


def is_password_strong(password):
    if len(password) < 8 or \
            not re.search(r"[a-z]", password) or \
            not re.search(r"[A-Z]", password) or \
            not re.search(r"\d", password) or \
            not re.search(r"[!@#$%^&*()-+{}|\"<>]?", password):
        return False
    return True


@app.route('/')
def navbar():
    return render_template('base.html')


class User:
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


class SigninForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Signin')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=15)])
    submit = SubmitField('Login')


@app.route('/signup/', methods=['GET', 'POST'])
def signup():
    form = SigninForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if not is_password_strong(password):
            flash('Password should be 8 characters long with upper case, lower case, and special characters.', 'danger')
            return redirect(url_for('signup'))
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        cur.execute('SELECT id FROM signup WHERE name = %s', (username,))
        old_user = cur.fetchone()
        if old_user:
            cur.close()
            flash('Username already taken. Please choose a different one.', 'danger')
            return render_template('signup.html', form=form)
        cur.execute('INSERT INTO signup (name, password) VALUES (%s, %s)', (username, hashed_password))
        mysql.connection.commit()
        cur.close()
        flash('Signup Successful', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html', form=form)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        cur = mysql.connection.cursor()
        cur.execute('SELECT id, name, password FROM signup WHERE name = %s', (username,))
        login_id = cur.fetchone()
        cur.close()
        if login_id:
            saved_password = login_id[2]
            if check_password_hash(saved_password, password):
                user = User(id=login_id[0], username=login_id[1], password=login_id[2])
                session['name'] = user.username
                return redirect(url_for('table'))
        flash('Invalid Credentials', 'danger')
    return render_template('login.html', form=form)


@app.route('/add/', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name = request.form['name']
        fund_code = request.form['code']
        invested_amount = int(request.form['amount'])
        units_held = int(request.form['unitheld'])
        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO funds (name, fund_code, invested_amount, units_held) VALUES (%s, %s, %s, %s)', (name, fund_code, invested_amount, units_held))
        mysql.connection.commit()
        cur.close()
        flash('Details successfully added', 'success')
        return redirect(url_for('table'))

    return render_template('add.html')
 
@app.route('/table/')
def table():
    if isloggedin():
        username = session['name']
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM funds WHERE name = %s', (username,))
        data = cur.fetchall()

        mf_list.clear()

        for info in data:
            id = info[0]
            name = info[1]
            code = info[2]
            amount = info[3]
            u_held = info[4]

            complete_url = api_url + str(code)
            detail = requests.get(complete_url)
            fund_name = detail.json().get('meta')['fund_house']
            nav = float(detail.json().get('data')[0].get('nav'))
            current_value = nav * u_held
            growth = current_value - amount

            funds_dict = {}
            funds_dict['id'] = id
            funds_dict['name'] = name
            funds_dict['Fund_name'] = fund_name
            funds_dict['Invested_amount'] = amount
            funds_dict['Unit_held'] = u_held
            funds_dict['Nav'] = nav
            funds_dict['Current_value'] = current_value
            funds_dict['Growth'] = growth
            mf_list.append(funds_dict)
            cur.close()
            
    return render_template('table.html',  data = mf_list)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM funds WHERE id = %s", (id,))
    data = cur.fetchone()
    cur.close()

    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        invested = int(request.form['amount'])
        units_held = int(request.form['unitheld'])

        complete_url = api_url + str(code)
        detail = requests.get(complete_url).json()
        fund_name = detail['meta']['fund_house']
        nav = float(detail['data'][0]['nav'])
        current_value = nav * units_held
        growth = current_value - invested

        cur = mysql.connection.cursor()
        cur.execute('UPDATE funds SET name = %s, fund_code = %s, invested_amount = %s, units_held = %s WHERE id = %s', (name, code, invested, units_held, id))
        mysql.connection.commit()
        cur.close()

        for fund in mf_list:
            if fund['id'] == id:
                fund['name'] = name
                fund['Fund_name'] = fund_name
                fund['Invested_amount'] = invested
                fund['Unit_held'] = units_held
                fund['Nav'] = nav
                fund['Current_value'] = current_value
                fund['Growth'] = growth
                break

        flash('Details successfully updated', 'success')
        return redirect(url_for('table'))

    return render_template('edit.html', data=data)


@app.route("/delete/<int:id>", methods=["GET", "POST"])
def remove(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM funds WHERE id = %s', (id,))
    mysql.connection.commit()
    cur.close()

    flash('Details successfully deleted', 'success')
    return redirect(url_for("table"))

@app.route('/logout/')
def logout():
    session.pop('name', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
