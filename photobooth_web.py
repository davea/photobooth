from configparser import ConfigParser

from flask import Flask, request, render_template
app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return "saved!"
    else:
        config = ConfigParser()
        config.read("config.ini")
        return render_template("index.html", config=config)

if __name__ == '__main__':
    app.run()
