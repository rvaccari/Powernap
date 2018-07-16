from setuptools import setup


if __name__ == '__main__':
    setup(
        name='powernap',
        version='2.0.8',
        author='Zachary Kazanski',
        author_email='kazanski.zachary@gmail.com',
        description='Framework for quickly buidling REST-ful APIs in Flask.',
        url="https://github.com/kazanz/powernap",
        packages=[
            "powernap",
            "powernap.architect",
            "powernap.auth",
            "powernap.query"
        ],
        install_requires=[
            'requests>=2.13.0',
            'six>=1.10.0',
            'bleach>=1.5.0',
            'Flask-Cors>=2.0.1',
            'Flask-SQLAlchemy>=2.1.0',
            'Flask-Login>=0.4.0',
            'SQLAlchemy>=1.1.5',
            'flask>=0.12.0',
            'Flask-GraphQL>=1.4.1',
            'graphene>=2.0.1',
            'graphene-sqlalchemy>=2.0.0',
        ],
        classifiers=[
            'Programming Language :: Python',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 3.5',
        ],
    )
