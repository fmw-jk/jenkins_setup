#!/bin/bash
echo "Installing TurboVNC Version 1.1.95 (1.2rc)"

# Figure out architecture and set the url accordingly
case "`dpkg --print-architecture`" in
"amd64")
    echo "Using 64-bit version"
    pkg="$DIR/../tvnc/turbovnc_1.1.95_amd64.deb"
    ;;
*)
    echo "Using 32-bit version"
    pkg="$DIR/../tvnc/turbovnc_1.1.95_i386.deb"
    ;;
esac

# Install turbovnc dependencies
sudo apt-get install -y xauth xfonts-base

# Install the package
sudo dpkg -i $pkg

# Copy passwd file
mkdir -p ~/.vnc
cp $DIR/tvnc/vncpasswd ~/.vnc/passwd
cp $DIR/tvnc/xstartup.turbovnc ~/.vnc/
user=`whoami`
if [ -z "$user" ]; then 
    user='jenkins'
fi
chown -R $user:$user ~/.vnc

[ -f /opt/TurboVNC/bin/vncserver ]
