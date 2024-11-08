from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify(message="Welcome to ParkEase API!")

@app.route('/test')
def test():
    
    return jsonify(message="API is workings!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
