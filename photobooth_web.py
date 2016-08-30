from configparser import ConfigParser
import subprocess

from flask import Flask, request, render_template, flash, redirect, url_for
app = Flask(__name__)
app.secret_key = "1TdvGMjAYhnTkL`XS1-q{FPv4il(Q1mZy["

def photobooth_status():
    output = b"unknown photobooth status"
    try:
        output = subprocess.check_output("sudo supervisorctl status photobooth", stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        app.logger.exception("Couldn't check status of photobooth service.")
        output = e.output
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    return " ".join(output.split())

def restart_photobooth():
    try:
        output = subprocess.check_output("sudo supervisorctl restart photobooth", stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        app.logger.exception("Couldn't restart photobooth service.")
        output = e.output
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    return " ".join(output.split())

def read_config():
    config = ConfigParser()
    config.read("config.ini")
    return config

def write_config():
    config = ConfigParser()
    for param, value in request.form.items():
        section, name = param.split(".")
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, name, value)
    with open("config.ini", "w") as configini:
        config.write(configini)

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        write_config()
        flash(restart_photobooth())
        return redirect(url_for('index'))
    config = read_config()
    return render_template("index.html", config=config, status=photobooth_status())

if __name__ == '__main__':
    app.run()
