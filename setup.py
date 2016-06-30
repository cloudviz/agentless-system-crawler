
from setuptools import setup, find_packages

setup(
    name='agentless-system-crawler',
    version='0.0.1.dev',
    #description='',
    #long_description=long_description,
    author='IBM',
    #author_email='',
    license='apache2',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
    ],
    packages = find_packages(),
    install_requires=['psutil','netifaces',],
    
    setup_requires=['pytest-runner>=2.0,<3dev',],
    tests_require=['pytest',],
    use_2to3=True,
)
