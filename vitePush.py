import os
import shutil
import stat
from git import Repo
from ftplib import FTP, error_perm
import time

# 配置参数
GIT_REPO_URL = ''
FOLDER_NAME = '.vitepress/dist'
LOCAL_CLONE_DIR = './clone'
FTP_SERVER = ''
FTP_USER = ''
FTP_PASS = ''
FTP_UPLOAD_DIR = '/'  # 请根据需要修改

def make_writable(filepath):
    # 将文件或目录的权限设置为可写
    os.chmod(filepath, stat.S_IWRITE)

# 递归修改目录和文件的权限为可写
def make_directory_writable(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            make_writable(dir_path)
        for file in files:
            file_path = os.path.join(root, file)
            make_writable(file_path)

# 删除只读文件时的处理函数
def remove_readonly(func, path, excinfo):
    # 如果删除的是文件或目录，尝试修改权限为可写，然后重新删除
    if func == os.remove or func == os.rmdir:
        make_writable(path)
        func(path)
    else:
        raise

# 克隆仓库的函数
def clone_repo():
    # 如果目标目录已存在，删除它
    if os.path.exists(LOCAL_CLONE_DIR):
        print(f"正在删除目录 {LOCAL_CLONE_DIR}")
        
        # 先递归修改目录中的文件权限为可写
        make_directory_writable(LOCAL_CLONE_DIR)
        
        # 然后使用 shutil.rmtree 删除目录
        shutil.rmtree(LOCAL_CLONE_DIR, onerror=remove_readonly)  # 使用自定义删除处理函数

    # 确保目标目录没有权限问题，若不存在则创建
    if not os.path.exists(LOCAL_CLONE_DIR):
        os.makedirs(LOCAL_CLONE_DIR)  # 创建目录

    print(f"克隆仓库 {GIT_REPO_URL} 到 {LOCAL_CLONE_DIR}")
    
    # 在克隆之前，确保目标目录是可写的
    make_writable(LOCAL_CLONE_DIR)
    
    # 克隆仓库
    try:
        Repo.clone_from(GIT_REPO_URL, LOCAL_CLONE_DIR)
        print(f"仓库克隆成功！")
    except Exception as e:
        print(f"克隆仓库时出现错误: {e}")

def connect_ftp():
    """
    连接到FTP服务器并进行登录。
    
    :return: 已连接的FTP对象
    """
    ftp = FTP(FTP_SERVER)
    ftp.login(FTP_USER, FTP_PASS)
    return ftp

def upload_folder_to_ftp(ftp, folder_to_upload):
    # 遍历并上传文件夹内容
    for root, dirs, files in os.walk(folder_to_upload):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # 计算相对路径
            relative_path = os.path.relpath(root, folder_to_upload)
            ftp_upload_path = os.path.join(FTP_UPLOAD_DIR, relative_path, filename).replace(os.sep, '/')
            
            # 创建远程目录（如果不存在）
            remote_dirs = ftp_upload_path.split('/')[:-1]
            current_path = FTP_UPLOAD_DIR
            
            for dir_part in remote_dirs:
                current_path = os.path.join(current_path, dir_part)
                try:
                    # 尝试进入目录
                    ftp.cwd(current_path)
                except error_perm:
                    # 目录不存在则创建
                    try:
                        ftp.mkd(current_path)
                        ftp.cwd(current_path)
                    except error_perm as e:
                        print(f"无法创建目录 {current_path} 或没有权限: {e}")
                        break
            
            # 上传文件
            try:
                with open(filepath, 'rb') as f:
                    ftp.storbinary(f'STOR {os.path.basename(ftp_upload_path)}', f)
                print(f"文件 {ftp_upload_path} 上传成功")
            except Exception as e:
                print(f"上传文件时出错 {filepath}: {e}")
            
            # 回到初始目录
            ftp.cwd(FTP_UPLOAD_DIR)

def sync_repo_to_ftp(retry_limit=3, retry_delay=5):
    clone_repo()
    folder_to_upload = os.path.join(LOCAL_CLONE_DIR, FOLDER_NAME)
    
    retry_count = 0
    while retry_count < retry_limit:
        try:
            ftp = connect_ftp()
            ftp.cwd(FTP_UPLOAD_DIR)

            upload_folder_to_ftp(ftp, folder_to_upload)

            ftp.quit()
            print("上传完成！")
            break

        except Exception as e:
            print(f"出现错误：{e}")
            retry_count += 1
            if retry_count < retry_limit:
                print(f"尝试重新连接...({retry_count}/{retry_limit})")
                time.sleep(retry_delay)
            else:
                print("连接失败次数过多，请检查网络和服务器状态。")
    
    # 清理本地克隆的目录
    make_directory_writable(LOCAL_CLONE_DIR)
    shutil.rmtree(LOCAL_CLONE_DIR)

# 执行同步功能
sync_repo_to_ftp()
