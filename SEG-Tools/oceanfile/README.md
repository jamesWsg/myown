# create folder only 

* we support these mode :
* mkdir 
* write
* read
* rmdir
* rm 


# only mkdir 
```
dell-buildman oceanfile/round-1 ‹master› » ../oceanfile -d . -p 5 -a 10,10,10 -m mkdir 
---------------------------------------------
mkdir_success   :         1110
mkdir_eexist    :            0
mkdir_fail      :            0
---------------------------------------------
```

# only write file

-S mean skip mkdir. you must mkdir first ,then exec follow command

```
dell-buildman oceanfile/round-1 ‹master› » ../oceanfile -d . -p 5 -a 10,10,10,5 -S -s 4K 
---------------------------------------------
create_success  :         5000
create_eexist   :            0
create_fail     :            0
open_success    :         5000
open_fail       :            0
write_success   :         5000
write_fail      :            0
---------------------------------------------

```

# mkdir and write files
if the folds tree not exists, you need this command :
it will try to mkdir and then write file.

if user have alreay create folders , you will see mkdir_eexist is not zero

```
dell-buildman oceanfile/round-1 ‹master*› » ../oceanfile -d . -p 5 -a 10,10,10,5 -s 4K       
---------------------------------------------
mkdir_success   :         1110
mkdir_eexist    :            0
mkdir_fail      :            0
create_success  :         5000
create_eexist   :            0
create_fail     :            0
open_success    :         5000
open_fail       :            0
write_success   :         5000
write_fail      :            0
---------------------------------------------

```

# rm files and dir 

if you want to delete files and folders ,you need rm mode

if will try to delete file ,then delete it parent folder and parent folder...

```
dell-buildman oceanfile/round-1 ‹master*› » ../oceanfile -d . -p 5 -a 10,10,10,5 -m rm  
---------------------------------------------
remove_success  :         5000
remove_fail     :            0
rmdir_success   :         1110
rmdir_enoent    :            0
rmdir_enotempty :            0
rmdir_fail      :            0
---------------------------------------------
```

# rmdir 
if there a no file ,only directory exists ,you want delete them ,you need rmdir mode

```
dell-buildman oceanfile/round-1 ‹master*› » ../oceanfile -d . -p 5 -a 10,10,10 -m mkdir  
---------------------------------------------
mkdir_success   :         1110
mkdir_eexist    :            0
mkdir_fail      :            0
---------------------------------------------
dell-buildman oceanfile/round-1 ‹master*› » ../oceanfile -d . -p 5 -a 10,10,10 -m rmdir 
---------------------------------------------
rmdir_success   :         1110
rmdir_enoent    :            0
rmdir_enotempty :            0
rmdir_fail      :            0
---------------------------------------------

```
*	-S mean skip dir , we suppose the directory have already exist, no need to create it first

```
root@node2:/var/share/ezfs/shareroot/round-5# oceanfile -d . -p 5 -a 10,10,10,2 -S -s 1M -b 128K 
---------------------------------------------
create_success  :         2000
create_eexist   :            0
create_fail     :            0
open_success    :         2000
open_fail       :            0
write_success   :        16000
write_fail      :            0
---------------------------------------------
```

# I am not sure if the folder create or not ,just create folder and write files 

```
root@node2:/var/share/ezfs/shareroot/round-5# oceanfile -d . -p 5 -a 10,10,10,2 -s 1M -b 128K 
---------------------------------------------
mkdir_success   :            0
mkdir_eexist    :         1110
mkdir_fail      :            0
create_success  :            0
create_eexist   :         2000
create_fail     :            0
open_success    :         2000
open_fail       :            0
write_success   :        16000
write_fail      :            0
---------------------------------------------
```

# read the exists files

```
root@node2:/var/share/ezfs/shareroot/round-5# oceanfile -d . -m read -p 5 -a 10,10,10,2  -b 128K 
---------------------------------------------
open_success    :         2000
open_fail       :            0
stat_success    :         2000
stat_fail       :            0
read_success    :        16000
read_fail       :            0
---------------------------------------------
```
