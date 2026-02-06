from setuptools import setup, find_packages

setup(
    name="txa-m",
    version="2.1.4",
    packages=find_packages(),
    install_requires=[
        "requests",
        "gazpacho",
        "rich"
    ],
    include_package_data=True,
    package_data={
        "txa_mediafire": ["*.json"],
    },
    entry_points={
        "console_scripts": [
            "txa-m=txa_mediafire.cli:main",
        ],
    },
    author="TXA",
    author_email="viptretrauc@gmail.com",
    license="MIT",
    description="A modern, high-speed downloader for MediaFire files and folders",
    long_description=open("README.md", encoding="utf-8").read() if open("README.md", encoding="utf-8") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/TXAVLOG/TXA-MEDIAFIRE",
    project_urls={
        "Bug Tracker": "https://github.com/TXAVLOG/TXA-MEDIAFIRE/issues",
        "Source Code": "https://github.com/TXAVLOG/TXA-MEDIAFIRE",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Operating System :: Android",
    ],
    python_requires='>=3.10, <=3.14.3',
)
