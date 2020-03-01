#
# Ubuntu Dockerfile
#
# https://github.com/dockerfile/ubuntu
#

# Pull base image.
FROM ubuntu:14.04



ADD root/sources.list /etc/apt/sources.list
ADD root/trusted.gpg.d /etc/apt/trusted.gpg.d

ADD root/apt-get-install_deb.sh /root/apt-get-install_deb.sh

RUN bash /root/apt-get-install_deb.sh
# Install.


# Add files.
ADD root/.bashrc /root/.bashrc
ADD root/.gitconfig /root/.gitconfig
ADD root/.scripts /root/.scripts
ADD root/.ssh /root/.ssh
ADD root/kernel-package_13.014+nmu1_all.deb /root/kernel-package_13.014+nmu1_all.deb
#RUN dpkg -i /root/kernel-package_13.014+nmu1_all.deb

# for modify the above deb conf
ADD root/postinst /usr/share/kernel-package/pkg/image/postinst
# Set environment variables.
ENV HOME /root

# Define working directory.
WORKDIR /root

# Define default command.
CMD ["bash"]
