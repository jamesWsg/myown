# Open JDK 安装

## 下载 Open JDK

* 因为java licence问题需要使用Open JDK
* Elasticsearch建议使用LTS版本Java，如Java8
* 因为我没找到合适的编译好的open jdk8，所以才使用open jdk9

## 上传至一个node的 `/opt` 目录

```
# ls
openjdk-9.0.4_linux-x64_bin.tar.gz
# 

```

## 解压缩
```
tar xvf openjdk-9.0.4_linux-x64_bin.tar.gz 
```

## 添加软链接便于以后升级替换JDK

```
ln -s /opt/jdk-9.0.4 /opt/java
```

## 设置JAVA相关的环境变量
在 `/etc/profile` 文件最后加上

```
export JAVA_HOME=/opt/java
export PATH=$PATH:/opt/java/bin
```
运行 `source /etc/profile` 重新加载环境变量

## 验证安装


```
#java -version
openjdk version "9.0.4"
OpenJDK Runtime Environment (build 9.0.4+11)
OpenJDK 64-Bit Server VM (build 9.0.4+11, mixed mode)

#javac -version
javac 9.0.4
```

如果能正常显示Java版本信息即可；否则要检查前面步骤
