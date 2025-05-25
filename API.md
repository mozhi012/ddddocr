# DdddOcr HTTP 服务 API 文档

本文档描述了通过 HTTP 调用 `ddddocr` 项目功能的 API 接口。
服务默认运行在 `http://localhost:5000` (如果在 Docker 容器中运行，请确保端口映射正确)。

## 1. 服务状态检查与测试页面

- **URL:** `/`
- **方法:** `GET`
- **描述:** 返回一个 HTML 测试页面 (`examples.html`)，可用于直接在浏览器中测试各个 API 端点。请确保 `examples.html` 文件与服务应用 (`app.py`) 在同一目录中。
- **成功响应 (200 OK):**
  - **内容类型:** `text/html`
  - **内容:** `examples.html` 的完整内容。
- **错误响应 (如果 `examples.html` 未找到):**
  - **内容类型:** `text/html`
  - **内容:** 一个提示 `examples.html` 未找到的错误 HTML 页面。

## 2. 基础 OCR 识别

- **URL:** `/ocr/classification`
- **方法:** `POST`
- **描述:** 对提供的 Base64 编码的图片进行 OCR 识别。
- **请求类型:** `application/json`
- **JSON 请求体参数:**
    - `image_base64`: (必需, 字符串) 图片文件的 Base64 编码字符串。
    - `beta`: (可选, 布尔值, 默认 `false`) 是否使用第二套 OCR 模型。
    - `png_fix`: (可选, 布尔值, 默认 `false`) 是否为透明背景的 PNG 图片启用修复。
    - `probability`: (可选, 布尔值, 默认 `false`) 是否返回详细的字符概率信息。如果为 `true`，响应中的 `details` 字段将包含原始概率数据。
    - `ranges`: (可选, 字符串或整数) 指定 OCR 字符集范围。
        - 如果是整数 (例如 `0`, `1`, ..., `7`)，则对应预定义的字符集索引。
        - 如果是字符串 (例如 `"0123456789+-x/="`)，则为自定义字符集。
        - **注意:** 使用 `ranges` 参数会为当前请求动态创建一个新的 OCR 实例。
- **JSON 请求体示例:**
  ```json
  {
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "beta": false,
    "png_fix": true,
    "probability": true,
    "ranges": "0123456789"
  }
  ```
- **成功响应 (200 OK):**
  - **内容类型:** `application/json`
  - **示例 (probability=false):**
    ```json
    {
      "result": "abcd"
    }
    ```
  - **示例 (probability=true):**
    ```json
    {
      "result": "1234",
      "details": {
        "charsets": ["0", "1", "2", ..., "9", "a", ...],
        "probability": [
          [0.01, 0.9, 0.02, ...],
          [0.85, 0.05, 0.01, ...]
        ]
      }
    }
    ```
- **错误响应 (400 Bad Request / 415 Unsupported Media Type / 500 Internal Server Error):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "error": "错误描述信息"
    }
    ```

## 3. 目标检测

- **URL:** `/ocr/detection`
- **方法:** `POST`
- **描述:** 检测提供的 Base64 编码的图片中的目标主体位置。
- **请求类型:** `application/json`
- **JSON 请求体参数:**
    - `image_base64`: (必需, 字符串) 图片文件的 Base64 编码字符串。
- **JSON 请求体示例:**
  ```json
  {
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
  }
  ```
- **成功响应 (200 OK):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "bboxes": [
        [x1, y1, x2, y2],
        [x3, y3, x4, y4]
      ]
    }
    ```
- **错误响应 (400 Bad Request / 415 Unsupported Media Type / 500 Internal Server Error):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "error": "错误描述信息"
    }
    ```

## 4. 滑块检测 (算法1: 边缘匹配)

- **URL:** `/ocr/slide_match`
- **方法:** `POST`
- **描述:** 通过匹配 Base64 编码的滑块图像和背景图像的边缘找到坑位。适用于滑块图背景透明的情况。
- **请求类型:** `application/json`
- **JSON 请求体参数:**
    - `target_image_base64`: (必需, 字符串) 滑块图片的 Base64 编码字符串。
    - `background_image_base64`: (必需, 字符串) 背景图片的 Base64 编码字符串。
    - `simple_target`: (可选, 布尔值, 默认 `false`) 指示滑块图片是否为简单图像。
- **JSON 请求体示例:**
  ```json
  {
    "target_image_base64": "iVBORw0KGgoAAAAN...",
    "background_image_base64": "iVBORw0KGgoAAAAN...",
    "simple_target": false
  }
  ```
- **成功响应 (200 OK):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "result": {
        "target": [120, 55, 60, 60] 
      }
    }
    ```
- **错误响应 (400 Bad Request / 415 Unsupported Media Type / 500 Internal Server Error):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "error": "错误描述信息"
    }
    ```

## 5. 滑块检测 (算法2: 图像比较)

- **URL:** `/ocr/slide_comparison`
- **方法:** `POST`
- **描述:** 通过比较两张 Base64 编码的图片 (一张带坑位，一张不带坑位) 的不同之处来判断滑块目标坑位的位置。
- **请求类型:** `application/json`
- **JSON 请求体参数:**
    - `image_with_gap_base64`: (必需, 字符串) 带坑位图的 Base64 编码字符串。
    - `full_background_image_base64`: (必需, 字符串) 完整背景图的 Base64 编码字符串。
- **JSON 请求体示例:**
  ```json
  {
    "image_with_gap_base64": "iVBORw0KGgoAAAAN...",
    "full_background_image_base64": "iVBORw0KGgoAAAAN..."
  }
  ```
- **成功响应 (200 OK):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "result": {
        "target": [220, 150, 280, 210]
      }
    }
    ```
- **错误响应 (400 Bad Request / 415 Unsupported Media Type / 500 Internal Server Error):**
  - **内容类型:** `application/json`
  - **示例:**
    ```json
    {
      "error": "错误描述信息"
    }
    ```

## 如何运行服务

1.  **确保依赖已安装:** `pip install -r requirements.txt`
2.  **确保 `examples.html` 文件存在:** 将 `examples.html` 文件放置在与 `app.py` 相同的目录中。
3.  **直接运行 (开发模式):** `python app.py` (服务将在 `http://localhost:5000` 启动，访问此地址将显示测试页面)
4.  **使用 Gunicorn (生产模式推荐):** `gunicorn --workers 4 --bind 0.0.0.0:5000 "app:app"`
5.  **使用 Docker:**
    ```bash
    # 确保 app.py, requirements.txt, Dockerfile 和 examples.html 在当前目录
    # 构建 Docker 镜像
    docker build -t ddddocr-service .

    # 运行 Docker 容器
    docker run -p 5000:5000 ddddocr-service
    ```
    之后可以通过 `http://localhost:5000` 访问服务测试页面。 