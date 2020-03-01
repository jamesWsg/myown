# Elasticsearch安装文档(Ubuntu 12.04)

## 安装JDK
见安装JDK文档

## 使用root用户添加用户名为`elasticsearch`的用户

```
useradd -s  /bin/bash -m -d /home/elasticsearch elasticsearch
```


## 使用root用户改变系统设置

编辑`/etc/security/limits.conf` 在最后加上
```
elasticsearch    -       nofile          65536
```

编辑`/etc/pam.d/common-session` 在最后加上
```
session required pam_limits.so
```

编辑`/etc/sysctl.conf` 在最后加上
```
vm.max_map_count=655360
```

并执行命令`sysctl -p` 使用改动生效


## 使用root用户创建隐藏目录

```
#mkdir -p /var/share/ezfs/elasticsearch
chmod 777 /var/share/ezfs/elasticsearch
```


## 上传安装包

后面无特别说明都是使用`elasticsearch`用户操作

上传安装包至 /home/elasticsearch/目录
```
~$ ls /home/elasticsearch/
elasticsearch-6.2.2.tar.gz  elasticsearch-analysis-ik-6.2.2.zip

```

## 解开elasticsearch压缩包

```
tar xzvf elasticsearch-6.2.2.tar.gz
```


## 安装中文分词插件


```
cd elasticsearch-6.2.2
bin/elasticsearch-plugin install file:///home/elasticsearch/elasticsearch-analysis-ik-6.2.2.zip
```

## 修改elasticsearch监听IP
编辑`elasticsearch-6.2.2/config/elasticsearch.yml`文件，添加`network.host: 0.0.0.0` 

```
# ---------------------------------- Network -----------------------------------
#
# Set the bind address to a specific IP (IPv4 or IPv6):
#
#network.host: 192.168.0.1

network.host: 0.0.0.0

```


## 修改elasticsearch的cluster.name 和 node.name
编辑`elasticsearch-6.2.2/config/elasticsearch.yml`文件

```
#cluster.name名字可以自定义，集群内机器必须一致
cluster.name: bigtera-cluster

#node.name名字可以自定义，集群内机器名称要各不相同
node.name: node-1

```

## 修改elasticsearch的discovery.zen.ping.unicast.hosts
编辑`elasticsearch-6.2.2/config/elasticsearch.yml`文件

```
#集群内所有机器IP
discovery.zen.ping.unicast.hosts: ["172.17.59.72", "172.17.59.73","172.17.59.74"]

```


## 修改elasticsearch的discovery.zen.minimum_master_nodes
编辑`elasticsearch-6.2.2/config/elasticsearch.yml`文件

```
# minimum_master_nodes = nodes / 2 + 1
# 3台机器写2;4,5台写3；6,7台写4
discovery.zen.minimum_master_nodes: 2

```

## 修改elasticsearch的log和数据存方位置
编辑`elasticsearch-6.2.2/config/elasticsearch.yml`文件
注意要为每台机器指定不同的目录

```
path.data: /var/share/ezfs/elasticsearch/node-1/data
path.logs: /var/share/ezfs/elasticsearch/node-1/logs

```

## 生产环境修改JVM参数
编辑`elasticsearch-6.2.2/config/jvm.options`文件
功能测试环境默认即可

```
-Xms2g
-Xmx2g

```


## 以deamon的方式启动elasticsearch

```
bin/elasticsearch -d

```

## 验证elasticsearch是否正常运行


```
elasticsearch@andy-node-2:~$ curl -XGET 'localhost:9200/_cat/health?v&pretty'
epoch      timestamp cluster         status node.total node.data shards pri relo init unassign pending_tasks max_task_wait_time active_shards_percent
1522053329 16:35:29  bigtera-cluster green           3         3     20  10    0    0        0             0                  -                100.0%
elasticsearch@andy-node-2:~$ netstat -an|grep 9200
tcp        0      0 0.0.0.0:9200       0.0.0.0:*               LISTEN     
elasticsearch@andy-node-2:~$ curl -XGET 'localhost:9200/_cat/nodes?v&pretty'
ip           heap.percent ram.percent cpu load_1m load_5m load_15m node.role master name
172.17.59.74           45          93  25    1.05    1.78     1.93 mdi       -      node-3
172.17.59.72           45          93  16    1.50    1.82     1.96 mdi       -      node-1
172.17.59.73           48          95  25    1.96    1.99     2.00 mdi       *      node-2
elasticsearch@andy-node-2:~$

```

如果服务端口有，需要查看`logs/elasticsearch.log`中的内容查找原因


## 停止elasticsearch（需要的时候）
先查出PID，然后给进程发SIGTERM信号
```
$jps | grep Elasticsearch
$kill -SIGTERM   <pid>

```

## 设置Elasticsearch用户名密码访问 
请查看另外一个文档文件

