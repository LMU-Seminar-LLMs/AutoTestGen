FROM python:3.9.6

WORKDIR /app

RUN pip install coverage
RUN pip install pipreqs
CMD ["bash"]