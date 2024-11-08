import mysql.connector
from mysql.connector import Error

def test_mysql_connection(host, user, password):
    try:
        # Establish the connection
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        
        if connection.is_connected():
            print("Connection to MySQL database was successful!")
        else:
            print("Failed to connect to the database.")
    
    except Error as e:
        print(f"Error: {e}")
    
    finally:
        # Close the connection if it was established
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("MySQL connection is closed.")

# Replace with your actual MySQL details
host = 'tanzhizheng1520.mysql.pythonanywhere-services.com'
user = 'tanzhizheng1520'
password = 're2Super'

test_mysql_connection(host, user, password)
