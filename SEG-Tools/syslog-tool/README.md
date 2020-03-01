# TSYSLOG

## What

This is a tool to write messages to kern.log.

## Why

Sometimes, it is really hard to triggle some error like disk failure, ext4 error or memory leak etc. But we want to test how our product handle these errors when they are detected (by checking kern.log). By using this program, we can insert a fake message to kern.log to simulate an real error occurs.

## How

1. Go to syslog-tool folder, run

   ```shell
   make
   ```

2. Insert the kernel module:

   ```shell
   insmod tsyslog.ko mystring="AnyTextYouWant"
   ```

   The content after `mystring=` is the message to be written to kern.log. 

   **P.S.** If your message contains spaces, you must quote your message twice, like:

   ```shell
   insmod tsyslog.ko mystring='"Hello World"'
   ```

3. Now, check kern.log, you should see you message:

   ```shell
   Feb  8 12:18:12 26-63 kernel: [681580.166312] Hello World
   ```

4. If you changed your message and want to try again, you may see this error:

   ```shell
   insmod: error inserting 'tsyslog.ko': -1 File exists
   ```

   What you need to do is remove the old `.ko` file using `rmmod` command:

   ```shell
   rmmod tsyslog.ko
   ```

   ​

   ​