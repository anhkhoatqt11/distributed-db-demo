import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import time

# Cấu hình logging cơ bản
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load biến môi trường (ưu tiên từ OS, sau đó từ .env nếu có)
load_dotenv()

app = Flask(__name__)
# Cho phép CORS từ mọi nguồn (chỉ dùng cho demo, không nên cho production)
CORS(app)

# Lấy URL kết nối từ biến môi trường
DB_URLS = {
    'node1': os.getenv('DB_NODE1_URL', 'postgresql://user:yourpassword@localhost:5431/demodb'),
    'node2': os.getenv('DB_NODE2_URL', 'postgresql://user:yourpassword@localhost:5432/demodb'),
    'node3': os.getenv('DB_NODE3_URL', 'postgresql://user:yourpassword@localhost:5433/demodb'),
}

# Hàm kết nối đến DB, trả về connection và cursor
def get_db_connection(node_id):
    url = DB_URLS.get(node_id)
    if not url:
        logging.error(f"Không tìm thấy URL cho {node_id}")
        return None, None
    try:
        # Thêm timeout để tránh chờ quá lâu nếu node không sẵn sàng
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.autocommit = True # Bật autocommit cho demo đơn giản
        cur = conn.cursor()
        logging.info(f"Đã kết nối thành công đến {node_id}")
        return conn, cur
    except psycopg2.OperationalError as e:
        logging.error(f"Lỗi kết nối đến {node_id}: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Lỗi không xác định khi kết nối {node_id}: {e}")
        return None, None

# Hàm đóng kết nối
def close_db_connection(conn, cur):
    if cur:
        cur.close()
    if conn:
        conn.close()
    # logging.info("Đã đóng kết nối DB.") # Bỏ comment nếu muốn log chi tiết

# Hàm khởi tạo bảng (chạy một lần hoặc khi cần)
def initialize_table(node_id):
    conn, cur = get_db_connection(node_id)
    if conn and cur:
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logging.info(f"Đã kiểm tra/tạo bảng 'items' trên {node_id}")
        except Exception as e:
            logging.error(f"Lỗi khi tạo bảng trên {node_id}: {e}")
        finally:
            close_db_connection(conn, cur)
    else:
         logging.warning(f"Bỏ qua khởi tạo bảng trên {node_id} do lỗi kết nối.")

# Khởi tạo bảng trên tất cả các node khi ứng dụng khởi động
# Trong môi trường thực tế, việc này thường được quản lý bằng migration tools
# @app.before_first_request
def init_all_dbs():
    logging.info("Đang khởi tạo bảng trên các node...")
    for node_id in DB_URLS.keys():
         initialize_table(node_id)
    logging.info("Hoàn tất khởi tạo bảng.")

# API Endpoint để thêm item mới (Replication Logic)
@app.route('/items', methods=['POST'])
def add_item():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Thiếu trường 'name'"}), 400

    item_name = data['name']
    primary_node = 'node1' # Giả định node1 là primary hoặc điểm ghi đầu tiên
    nodes_to_replicate = ['node2', 'node3']
    success = False

    # 1. Ghi vào node chính (hoặc node đầu tiên)
    conn_p, cur_p = get_db_connection(primary_node)
    if conn_p and cur_p:
        try:
            cur_p.execute("INSERT INTO items (name) VALUES (%s)", (item_name,))
            # Không cần lấy ID vì chúng ta đang mô phỏng đơn giản
            logging.info(f"Đã ghi '{item_name}' vào {primary_node}")
            success = True
        except Exception as e:
            logging.error(f"Lỗi khi ghi vào {primary_node}: {e}")
        finally:
            close_db_connection(conn_p, cur_p)
    else:
         logging.warning(f"Không thể ghi vào {primary_node} do lỗi kết nối.")

    # 2. Ghi vào các node phụ (bất đồng bộ - mô phỏng)
    # Trong demo này, chúng ta thực hiện tuần tự nhưng không chờ đợi kết quả của các node phụ để trả về client
    # Để làm bất đồng bộ thực sự, cần dùng background tasks (Celery, RQ,...)
    if success: # Chỉ replicate nếu ghi vào primary thành công
        for node_id in nodes_to_replicate:
            conn_r, cur_r = get_db_connection(node_id)
            if conn_r and cur_r:
                try:
                    # Thêm chút delay để mô phỏng độ trễ mạng/xử lý
                    # time.sleep(0.1)
                    cur_r.execute("INSERT INTO items (name) VALUES (%s)", (item_name,))
                    logging.info(f"Đã replicate '{item_name}' đến {node_id}")
                except Exception as e:
                    logging.error(f"Lỗi khi replicate đến {node_id}: {e}")
                finally:
                    close_db_connection(conn_r, cur_r)
            else:
                logging.warning(f"Bỏ qua replicate đến {node_id} do lỗi kết nối.")
        # Trả về thành công cho client ngay cả khi replicate có thể chưa hoàn tất hoặc lỗi
        return jsonify({"message": "Item được thêm (đang replicate)", "name": item_name}), 201
    else:
        # Nếu không ghi được vào node chính, trả về lỗi
        return jsonify({"error": f"Không thể ghi item vào node chính ({primary_node})"}), 500

# API Endpoint để lấy items từ một node cụ thể
@app.route('/items/node/<node_id>', methods=['GET'])
def get_items_from_node(node_id):
    if node_id not in DB_URLS:
        return jsonify({"error": "Node ID không hợp lệ"}), 404

    conn, cur = get_db_connection(node_id)
    if conn and cur:
        try:
            cur.execute("SELECT id, name, created_at FROM items ORDER BY created_at DESC LIMIT 50") # Giới hạn số lượng
            items = cur.fetchall()
            # Chuyển đổi kết quả thành list các dict để dễ dàng JSON hóa
            items_list = [{"id": row[0], "name": row[1], "created_at": row[2].isoformat()} for row in items]
            return jsonify(items_list)
        except Exception as e:
            logging.error(f"Lỗi khi đọc từ {node_id}: {e}")
            return jsonify({"error": f"Lỗi khi đọc dữ liệu từ {node_id}"}), 500
        finally:
            close_db_connection(conn, cur)
    else:
        return jsonify({"error": f"Không thể kết nối đến {node_id}"}), 503 # Service Unavailable


@app.route('/items/search', methods=['GET'])
def search_items():
    # Lấy query tìm kiếm từ query parameter 'q'
    query = request.args.get('q')
    if not query or query.strip() == '':
        return jsonify({"error": "Thiếu query tìm kiếm 'q'"}), 400

    search_term = f"%{query.strip()}%" # Thêm wildcard % để tìm kiếm gần đúng (contains)
    found_items = {} # Dùng dict để tự động loại bỏ trùng lặp qua ID
    connection_errors = []

    logging.info(f"Bắt đầu tìm kiếm với query: '{query}'")

    # Lặp qua tất cả các node để tìm kiếm
    # (Giả sử dùng Cách 1 hoặc 2 từ lần sửa trước, DB_URLS keys là 'node1', 'node2',...)
    # Nếu keys là '1', '2', '3', bạn cần điều chỉnh logic lấy node_key
    node_keys_to_search = list(DB_URLS.keys()) # ['node1', 'node2', 'node3'] hoặc ['1', '2', '3']

    for node_key in node_keys_to_search:
        conn, cur = get_db_connection(node_key)
        if conn and cur:
            try:
                # Sử dụng ILIKE cho tìm kiếm không phân biệt hoa thường (PostgreSQL specific)
                # Hoặc dùng LOWER(name) LIKE LOWER(%s) cho tương thích rộng hơn
                sql_query = "SELECT id, name, created_at FROM items WHERE name ILIKE %s ORDER BY created_at DESC"
                cur.execute(sql_query, (search_term,))
                results = cur.fetchall()
                logging.info(f"Tìm thấy {len(results)} kết quả trên {node_key} cho query '{query}'")
                for row in results:
                    item_id = row[0]
                    # Nếu item chưa có trong dict hoặc bản ghi này mới hơn (tùy chọn)
                    # thì thêm/cập nhật vào dict. Ở đây chỉ cần thêm là đủ để deduplicate.
                    if item_id not in found_items:
                         found_items[item_id] = {
                            "id": item_id,
                            "name": row[1],
                            "created_at": row[2].isoformat(),
                            "found_on": [node_key] # Ghi nhận node đầu tiên tìm thấy
                         }
                    else:
                         # (Tùy chọn) Nếu muốn ghi nhận tất cả các node chứa item
                         if node_key not in found_items[item_id]["found_on"]:
                              found_items[item_id]["found_on"].append(node_key)

            except Exception as e:
                logging.error(f"Lỗi khi tìm kiếm trên {node_key}: {e}", exc_info=True)
                connection_errors.append(node_key)
            finally:
                close_db_connection(conn, cur)
        else:
            logging.warning(f"Bỏ qua tìm kiếm trên {node_key} do lỗi kết nối.")
            connection_errors.append(node_key)

    # Chuyển dict thành list để trả về JSON
    results_list = list(found_items.values())

    # Có thể thêm thông tin lỗi vào response nếu muốn
    response_data = {"results": results_list}
    if connection_errors:
        response_data["warnings"] = [f"Không thể tìm kiếm trên node: {err_node}" for err_node in set(connection_errors)]

    logging.info(f"Hoàn tất tìm kiếm, trả về {len(results_list)} item độc nhất.")
    return jsonify(response_data)

if __name__ == '__main__':
    # Lấy cổng từ biến môi trường hoặc dùng 5000 mặc định
    port = int(os.environ.get('PORT', 5000))
    with app.app_context(): # Đảm bảo có application context nếu cần
        init_all_dbs() # Gọi hàm khởi tạo bảng
    # Chạy app, host='0.0.0.0' để chấp nhận kết nối từ bên ngoài container
    app.run(host='0.0.0.0', port=port, debug=True) # Tắt debug=True trong production