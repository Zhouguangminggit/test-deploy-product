# 本地部署说明





> [!IMPORTANT]
>
> 部署前必须配置本地环境，安装uv以及nodejs22.10以上版本（‼️ ‼️）



### 环境配置



#### uv配置



> [!NOTE]
>
> 完整安装参考：https://hellowac.github.io/uv-zh-cn/getting-started/installation/#__tabbed_1_1
>
> 

##### windows环境：

1. 终端或者powershell执行命令：

   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   

2. 执行以后根据输出内容执行命令(cmd执行第一个， powershell执行第二个)：

   ```
   set Path=C:\UserslAdministratorl.locallbin;%Path%  (cmd)
   $env:Path ="c:\UserslAdministratorl.localbin;$env:Path" （powershell)
   ```

   

##### mac环境



1. ```
   执行： $ curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   



### nvm配置



推荐使用nvm管理nodejs版本，如果已经存在大于22.10版本的nodejs，可跳过配置



windows配置nvm参考：https://blog.csdn.net/weixin_43801036/article/details/142236194







### 执行脚本



配置好上述环境以后，打开源码项目，在终端执行命令等待输出结果：

```
python ./scripts/startup.py
```

