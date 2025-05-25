from flask import Flask, request, jsonify, send_from_directory, render_template_string
import ddddocr
import base64
import os # 用于读取 examples.html

app = Flask(__name__)

# --- 全局 OCR 实例 ---
# 说明: 根据 ddddocr 的 README 建议，DdddOcr 初始化应尽量少以优化性能。
# 对于需要不同配置（如 beta 模型, 自定义字符集 ranges）的 OCR 请求，
# 我们采取的策略是：
# 1. 对常用配置（默认模型、beta 模型）维护全局实例。
# 2. 对需要动态字符集 (ranges) 的请求，在该请求处理期间临时创建 DdddOcr 实例。
#    这虽然会增加单次请求的开销，但保证了灵活性和并发安全性，避免修改全局实例状态。

# 基础 OCR (默认模型)
ocr_default_global = ddddocr.DdddOcr()
# 基础 OCR (beta 模型)
ocr_beta_global = ddddocr.DdddOcr(beta=True)
# 目标检测模型 (关闭 OCR 功能以节省资源)
det_model_global = ddddocr.DdddOcr(det=True, ocr=False)
# 滑块检测模型 (关闭 OCR 和目标检测功能)
slide_model_global = ddddocr.DdddOcr(det=False, ocr=False)

# 用于缓存 examples.html 内容
EXAMPLES_HTML_CONTENT = None

def get_examples_html():
    # 辅助函数，用于读取并缓存 examples.html 的内容
    global EXAMPLES_HTML_CONTENT
    if EXAMPLES_HTML_CONTENT is None:
        try:
            # 假设 examples.html 与 app.py 在同一目录下
            # 在 Docker 环境中，它们会被复制到 /app 目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            examples_path = os.path.join(current_dir, "examples.html")
            if os.path.exists(examples_path):
                with open(examples_path, 'r', encoding='utf-8') as f:
                    EXAMPLES_HTML_CONTENT = f.read()
            else:
                app.logger.warning("examples.html not found at expected location.")
                EXAMPLES_HTML_CONTENT = "<!DOCTYPE html><html><head><title>Error</title></head><body><h1>Error: examples.html not found.</h1><p>Please ensure examples.html is in the same directory as app.py.</p></body></html>"

        except Exception as e:
            app.logger.error(f"Error reading examples.html: {e}")
            EXAMPLES_HTML_CONTENT = "<!DOCTYPE html><html><head><title>Error</title></head><body><h1>Error loading examples.html</h1></body></html>"
    return EXAMPLES_HTML_CONTENT


@app.route('/')
def index():
    # 服务运行状态检查端点，返回 examples.html 内容
    return render_template_string(get_examples_html())

@app.route('/ocr/classification', methods=['POST'])
def ocr_classification_endpoint():
    # OCR 识别接口 (接收 application/json)
    # JSON 请求体格式:
    # {
    #   "image_base64": "base64_encoded_image_string",
    #   "beta": false, (可选, 默认为 false)
    #   "png_fix": false, (可选, 默认为 false)
    #   "probability": false, (可选, 默认为 false)
    #   "ranges": null (可选, 例如 "0123456789" 或 "0")
    # }

    if not request.is_json:
        return jsonify({"error": "请求必须是 application/json 类型"}), 415 # Unsupported Media Type
    
    data = request.get_json()

    if not data or 'image_base64' not in data:
        return jsonify({"error": "缺少 image_base64 字段"}), 400

    try:
        image_bytes = base64.b64decode(data['image_base64'])
    except Exception as e:
        return jsonify({"error": f"无效的 Base64 图片数据: {str(e)}"}), 400

    if not image_bytes:
        return jsonify({"error": "图片数据解码后为空"}), 400

    # 解析可选参数
    use_beta_model = data.get('beta', False)
    png_fix = data.get('png_fix', False)
    return_probability = data.get('probability', False)
    custom_ranges_str = data.get('ranges', None)

    try:
        ocr_instance_to_use = None
        is_temp_instance = False

        if custom_ranges_str is not None:
            app.logger.info(f"动态创建 OCR 实例 (beta={use_beta_model}) 用于 ranges: '{custom_ranges_str}'")
            temp_ocr = ddddocr.DdddOcr(beta=use_beta_model)
            is_temp_instance = True
            try:
                ranges_value = int(custom_ranges_str)
            except ValueError:
                ranges_value = custom_ranges_str
            temp_ocr.set_ranges(ranges_value)
            ocr_instance_to_use = temp_ocr
        else:
            ocr_instance_to_use = ocr_beta_global if use_beta_model else ocr_default_global
        
        raw_result = ocr_instance_to_use.classification(image_bytes, png_fix=png_fix, probability=return_probability)
        
        final_response_data = {}
        if return_probability:
            if isinstance(raw_result, dict) and 'probability' in raw_result and 'charsets' in raw_result:
                result_str = ""
                charsets = raw_result['charsets']
                for prob_list_for_char_pos in raw_result['probability']:
                    if prob_list_for_char_pos and isinstance(prob_list_for_char_pos, list) and len(prob_list_for_char_pos) > 0:
                        if all(isinstance(p, (int, float)) for p in prob_list_for_char_pos):
                            max_prob_index = prob_list_for_char_pos.index(max(prob_list_for_char_pos))
                            if max_prob_index < len(charsets):
                                result_str += charsets[max_prob_index]
                            else:
                                app.logger.warning(f"字符集索引越界: max_prob_index={max_prob_index}, charsets 长度={len(charsets)}")
                                result_str += "?"
                        else:
                            app.logger.warning(f"概率列表中包含非数字类型元素: {prob_list_for_char_pos}")
                            result_str += "?"
                    else:
                         app.logger.warning(f"空的或无效的概率列表 encountered: {prob_list_for_char_pos}")
                         result_str += "?"
                final_response_data = {"result": result_str, "details": raw_result}
            else:
                app.logger.warning(f"请求了概率信息，但 ddddocr 返回的格式非预期: {type(raw_result)}")
                final_response_data = {"result": str(raw_result), "details": "原始输出，非标准概率格式"}
        else:
            final_response_data = {"result": str(raw_result)}
            
        return jsonify(final_response_data)

    except Exception as e:
        app.logger.error(f"OCR Classification Endpoint Error: {str(e)}", exc_info=True)
        return jsonify({"error": f"处理 OCR 请求时发生错误: {str(e)}"}), 500
    finally:
        if is_temp_instance and 'temp_ocr' in locals():
            app.logger.info(f"清理为 ranges '{custom_ranges_str}' 创建的临时 OCR 实例 (beta={use_beta_model})")
            del temp_ocr


@app.route('/ocr/detection', methods=['POST'])
def ocr_detection_endpoint():
    # 目标检测接口 (接收 application/json)
    # JSON 请求体格式:
    # {
    #   "image_base64": "base64_encoded_image_string"
    # }
    if not request.is_json:
        return jsonify({"error": "请求必须是 application/json 类型"}), 415
        
    data = request.get_json()

    if not data or 'image_base64' not in data:
        return jsonify({"error": "缺少 image_base64 字段"}), 400

    try:
        image_bytes = base64.b64decode(data['image_base64'])
    except Exception as e:
        return jsonify({"error": f"无效的 Base64 图片数据: {str(e)}"}), 400
    
    if not image_bytes:
        return jsonify({"error": "图片数据解码后为空"}), 400

    try:
        bboxes = det_model_global.detection(image_bytes)
        return jsonify({"bboxes": bboxes})
    except Exception as e:
        app.logger.error(f"OCR Detection Endpoint Error: {str(e)}", exc_info=True)
        return jsonify({"error": f"处理目标检测请求时发生错误: {str(e)}"}), 500

@app.route('/ocr/slide_match', methods=['POST'])
def ocr_slide_match_endpoint():
    # 滑块检测接口 (算法1: 边缘匹配, 接收 application/json)
    # JSON 请求体格式:
    # {
    #   "target_image_base64": "base64_encoded_target_image_string",
    #   "background_image_base64": "base64_encoded_background_image_string",
    #   "simple_target": false (可选, 默认为 false)
    # }
    if not request.is_json:
        return jsonify({"error": "请求必须是 application/json 类型"}), 415

    data = request.get_json()

    if not data or 'target_image_base64' not in data or 'background_image_base64' not in data:
        return jsonify({"error": "缺少 target_image_base64 或 background_image_base64 字段"}), 400

    try:
        target_bytes = base64.b64decode(data['target_image_base64'])
        background_bytes = base64.b64decode(data['background_image_base64'])
    except Exception as e:
        return jsonify({"error": f"无效的 Base64 图片数据: {str(e)}"}), 400

    if not target_bytes or not background_bytes:
        return jsonify({"error": "滑块或背景图片数据解码后为空"}), 400

    simple_target = data.get('simple_target', False)

    try:
        result = slide_model_global.slide_match(target_bytes, background_bytes, simple_target=simple_target)
        return jsonify({"result": result})
    except Exception as e:
        app.logger.error(f"Slide Match Endpoint Error: {str(e)}", exc_info=True)
        return jsonify({"error": f"处理滑块匹配 (算法1) 请求时发生错误: {str(e)}"}), 500

@app.route('/ocr/slide_comparison', methods=['POST'])
def ocr_slide_comparison_endpoint():
    # 滑块检测接口 (算法2: 图像比较, 接收 application/json)
    # JSON 请求体格式:
    # {
    #   "image_with_gap_base64": "base64_encoded_image_with_gap_string",
    #   "full_background_image_base64": "base64_encoded_full_background_image_string"
    # }
    if not request.is_json:
        return jsonify({"error": "请求必须是 application/json 类型"}), 415
        
    data = request.get_json()

    if not data or 'image_with_gap_base64' not in data or 'full_background_image_base64' not in data:
        return jsonify({"error": "缺少 image_with_gap_base64 或 full_background_image_base64 字段"}), 400
    
    try:
        bytes_with_gap = base64.b64decode(data['image_with_gap_base64'])
        bytes_full_background = base64.b64decode(data['full_background_image_base64'])
    except Exception as e:
        return jsonify({"error": f"无效的 Base64 图片数据: {str(e)}"}), 400

    if not bytes_with_gap or not bytes_full_background:
        return jsonify({"error": "图片数据解码后为空"}), 400

    try:
        result = slide_model_global.slide_comparison(bytes_with_gap, bytes_full_background)
        return jsonify({"result": result})
    except Exception as e:
        app.logger.error(f"Slide Comparison Endpoint Error: {str(e)}", exc_info=True)
        return jsonify({"error": f"处理滑块比较 (算法2) 请求时发生错误: {str(e)}"}), 500

if __name__ == '__main__':
    # 开发时可以直接运行此脚本。
    # 生产环境部署时，建议使用 Gunicorn 或 uWSGI 等 WSGI 服务器。
    # 例如: gunicorn --workers 4 --bind 0.0.0.0:5000 "app:app"
    # debug=True 会启用 Flask 的调试模式，方便开发，但在生产环境中应关闭。
    # 确保在运行前 examples.html 文件存在于 app.py 同级目录
    get_examples_html() # 预加载 HTML 内容或检查文件是否存在
    app.run(host='0.0.0.0', port=5000, debug=True) 