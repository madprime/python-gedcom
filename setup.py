from distutils.core import setup

setup(
    name='python-gedcom',
    version='0.1.1dev',
    packages=['gedcom',],
    license='GPLv2',
    package_dir={'': '.'},
    description=open('README').readlines()[0].strip(),
    long_description=open('README').read(),
    maintainer='Madeleine Ball',
    maintainer_email='mpball@gmail.com',
    url='https://github.com/madprime/python-gedcom',
)
