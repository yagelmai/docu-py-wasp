from setuptools import setup, find_packages
import py_wasp

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('requirements.txt') as requirements_file:
    requirements = [r.strip() for r in requirements_file.read().split('\n') if r.strip()]

setup(
    author='Yaniv Kimhi, Boris Serafimov',
    author_email='yaniv.kimhi@intel.com, boris.k.serafimov@intel.com',
    python_requires='>=3.6',
    classifiers=[
        'License :: Other/Proprietary License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    description="Python bindings for WASP",
    install_requires=requirements,
    license="Other/Proprietary License",
    long_description='\n' + readme,
    long_description_content_type="text/markdown",
    include_package_data=False,
    keywords='WASP',
    name='py-wasp',
    packages=find_packages(include=['py_wasp']),
    url='https://github.com/intel-innersource/libraries.python.py-wasp',
    version=py_wasp.__version__,
    platforms=['Any'],
    zip_safe=False,
)
