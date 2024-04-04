from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()
with open("requirements.txt", encoding="utf-8") as f:
    requirements = f.readlines()
setup(
    name="deccom",
    version="0.0.1",
    description="Decentralized Communication With Modular Protocol Stack.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Nikolay Blagoev",
    author_email="nickyblagoev@gmail.com",
    license="MIT",
    url="https://github.com/NikolayBlagoev/DecCom-Python",
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
      "Intended Audience :: Developers",
      "License :: OSI Approved :: MIT License",
      "Operating System :: OS Independent",
      "Programming Language :: Python",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.5",
      "Programming Language :: Python :: 3.6",
      "Programming Language :: Python :: 3.7",
      "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)