import mysql.connector
from mysql.connector import Error

def test_mysql_connection_and_fetch_data(host, user, password):
    try:
        # Establish the connection
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database='your_database_name'  # Replace with your actual database name
        )
        
        if connection.is_connected():
            print("Connection to MySQL database was successful!")

            # Create a cursor object
            cursor = connection.cursor()

            # Execute the SELECT query
            cursor.execute("SELECT * FROM reservations;")

            # Fetch all the records
            records = cursor.fetchall()

            # Print the records
            print("Data in reservations table:")
            for row in records:
                print(row)

            # Close the cursor
            cursor.close()

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

test_mysql_connection_and_fetch_data(host, user, password)
