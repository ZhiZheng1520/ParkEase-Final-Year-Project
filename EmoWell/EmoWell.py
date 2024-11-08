from flask import Flask
import mysql.connector
from mysql.connector import Error
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)




# ////////////////////////MYSQL CONNECTION/////////////////////////////////
# Type link "https://emowell-tanzhizheng1520.pythonanywhere.com/test"

db_config = {
    'host': 'tanzhizheng1520.mysql.pythonanywhere-services.com',
    'user': 'tanzhizheng1520',
    'password': 're2Super',
    'database': 'tanzhizheng1520$EmoWell'
}

def create_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            logging.debug("Connected to MySQL database")
            return connection
    except Error as e:
        logging.error(f"Error connecting to MySQL: {e}")
        return None
# //////////////////////////////////////////////////////////////////////////






# //////////////////////// MY SQL & API TEST/////////////////////////////////
@app.route('/test', methods=['GET'])
def test_route():
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # Example SQL query (modify this based on your schema)
            cursor.execute("SELECT DATABASE();")
            result = cursor.fetchone()
            logging.debug(f"SQL query result: {result}")
            return f"Connected to the database: {result[0]}"
        except Error as e:
            logging.error(f"SQL query error: {e}")
            return "Error running the SQL query", 500
        finally:
            cursor.close()
            connection.close()
    else:
        return "Failed to connect to the database", 500
# //////////////////////////////////////////////////////////////////////////






# /////////////////////////////HOST API/////////////////////////////////////
if __name__ == '__main__':
    logging.debug("Starting the Flask application")
    app.run(host='0.0.0.0', port=5000, debug=True)
# //////////////////////////////////////////////////////////////////////////
