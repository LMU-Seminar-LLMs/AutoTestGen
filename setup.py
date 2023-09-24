from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='AutoTestGen',
    version='0.1',
    description='Automatic Unit Test generation using LLM',
    long_description=long_description,
    author='Giorgi Nozadze',
    author_email='giorginozadze23@yahoo.com',
    license='MIT',
    url='https://github.com/LMU-Seminar-LLMs/AutoTestGen',
    packages=find_packages(),
    # Entry point
    entry_points={
        "console_scripts": [
            "autotestgen = AutoTestGen.gui:main"
        ]
    },
    install_requires=[
        "openai",
        "tiktoken",
        "docker",
        "python-dotenv",
        "coverage"
    ],
    package_data={"AutoTestGen": ["_run_tests_script.py"]},
    python_requires='>=3.9'
)