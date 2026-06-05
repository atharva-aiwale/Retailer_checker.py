# Retailer_checker.py
This project involves process automation. We need to enter a user ID and access the retailer list in the Identity Center on Chrome. From there, it will check if the user has access to a specific retailer and provide an output indicating "yes" or "no." This approach helps reduce the workflow time for the process.

Key requirements for the system to run this code:
1. You need to have Python version 3.14.1 or higher installed.
2. You must download pip Selenium on your system.

Problem Faced :
The identity center features a login page, but when the code runs, it gets stuck on this page. I modified the code to include the login ID and password; however, it still prompts for a verification code when the login button is clicked. This process took a considerable amount of time, and Selenium returned an error. To address this, I implemented a change that causes the code to pause for 120 seconds when the login page appears, allowing the user to manually log in to the identity center during this time.
