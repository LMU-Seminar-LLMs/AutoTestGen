FROM python:3.9.6

# Install the 'coverage' library using pip
RUN pip install coverage


# Install all other dependancies of your project you wish to test
# For example Copy the requirements.txt file into the container and install it 
COPY requirements.txt .
RUN pip install -r requirements.txt


CMD ["bash"]