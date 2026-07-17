# Cloudflare R2 媒体文件存储

后端支持在本地文件系统与 Cloudflare R2 之间切换。默认仍使用
`backend/media/`；只有显式设置 `USE_R2_STORAGE=true` 才会启用 R2。

现有 Flutter/Web 上传 API 和数据库字段无需调整。启用后，Django 的
`ImageField`、`FileField` 会把对象写入 R2，数据库继续保存
`product_images/...`、`designs/...` 等 object key。

## 1. 创建 R2 Bucket

1. 在 Cloudflare 控制台进入 **R2 Object Storage**。
2. 创建 Standard Bucket，例如 `work-order-media`。
3. 保持 Public Development URL 和 Public Bucket 关闭。
4. 创建仅限该 Bucket 的 Object Read & Write API Token。
5. 立即保存 Access Key ID 和 Secret Access Key；Secret 之后无法再次查看。

## 2. 配置后端

将以下配置写入部署环境的密钥管理系统或未提交的 `.env`：

```dotenv
USE_R2_STORAGE=true
R2_ACCOUNT_ID=your-cloudflare-account-id
R2_ACCESS_KEY_ID=your-r2-access-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
R2_BUCKET_NAME=work-order-media
R2_REGION_NAME=auto
R2_SIGNED_URL_EXPIRE_SECONDS=900
```

默认 endpoint 为：

```text
https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

EU 或 FedRAMP jurisdiction Bucket 需要通过 `R2_ENDPOINT_URL` 设置对应
endpoint。所有 R2 配置都只从环境变量读取，禁止将真实密钥提交到仓库。

## 3. 安装与验证

```bash
pip install -r requirements.txt
python manage.py check
pytest workorder/tests/test_storage_settings.py -q
```

配置真实凭证后，可在 Django shell 做一次隔离验证：

```python
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

key = default_storage.save("r2-smoke-test/hello.txt", ContentFile(b"hello"))
print(key)
print(default_storage.url(key))
default_storage.delete(key)
```

输出 URL 应包含 `X-Amz-Signature` 等签名参数，且删除后 R2 控制台中不再存在
测试对象。

## 4. 迁移现有文件

切换前，将 `backend/media/` 的内容按原相对路径复制到 R2。必须保留现有
object key，例如本地的 `backend/media/product_images/a.jpg` 应上传为
`product_images/a.jpg`，这样数据库无需批量修改。

迁移和切换期间暂停新上传，完成后抽样验证图片预览、附件下载、替换与删除。
确认无误前保留本地媒体目录备份。

## 安全要求

- Bucket 必须保持私有，通过短时签名 URL 访问。
- API Token 只授权目标 Bucket 的对象读写，不能使用账户级管理 Token。
- 不记录签名 URL、Access Key 或 Secret Access Key。
- 签名 URL 是临时 bearer token，敏感文件应使用较短有效期。
- 现有文件上传仍需在 Django 侧校验大小、扩展名、MIME 与真实内容。
