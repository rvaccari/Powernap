from setuptools import setup

if __name__ == '__main__':
    setup(
        name='powernap',
        version='1.0.0',
        author='Zachary Kazanski',
        author_email='kazanski.zachary@gmail.com',
        description='Framework for quickly buidling REST-ful APIs in Flask.',
        url="https://github.com/kazanz/powernap",
        packages=['powernap'],
        install_requires=[
            'requests>=2.9.1',
            'six>=1.10.0',
            'flask>=0.10.1',
            'SQLAlchemy>=1.0.11',
            'Flask-SQLAlchemy>=2.1',
            'Flask-Login>=0.2.11',
        ],
        classifiers=[
            'Programming Language :: Python',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 3.5',
        ],
    )
