// Địa chỉ của backend API
const API_BASE_URL = 'http://localhost:5000'; // Đảm bảo backend chạy trên cổng này

const itemNameInput = document.getElementById('item-name');
const addItemBtn = document.getElementById('add-item-btn');
const statusMessage = document.getElementById('status-message');
const nodeDisplays = {
    1: document.getElementById('node-1-data'),
    2: document.getElementById('node-2-data'),
    3: document.getElementById('node-3-data')
};
const refreshButtons = document.querySelectorAll('.refresh-btn');
const searchTermInput = document.getElementById('search-term');
const searchBtn = document.getElementById('search-btn');
const searchResultsDisplay = document.getElementById('search-results');

// Hàm hiển thị thông báo trạng thái
function showStatus(message, isError = false) {
    statusMessage.textContent = message;
    statusMessage.style.color = isError ? 'red' : 'green';
    // Tự động xóa thông báo sau vài giây
    setTimeout(() => { statusMessage.textContent = ''; }, 5000);
}

// Hàm fetch dữ liệu từ một node cụ thể
async function fetchDataForNode(nodeId) {
    const displayElement = nodeDisplays[nodeId];
    if (!displayElement) return;

    displayElement.textContent = 'Đang tải...'; // Hiển thị trạng thái loading
    try {
        const response = await fetch(`${API_BASE_URL}/items/node/node${nodeId}`); // Thêm 'node' vào trước nodeId
        if (!response.ok) {
            // Thử đọc lỗi từ server nếu có
            let errorMsg = `Lỗi ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                errorMsg = `Lỗi ${response.status}: ${errorData.error || response.statusText}`;
            } catch(e) { /* Bỏ qua nếu không parse được json lỗi */ }
             throw new Error(errorMsg);
        }
        const items = await response.json();
        // Hiển thị dữ liệu (ví dụ: dạng JSON hoặc format đẹp hơn)
        //displayElement.textContent = JSON.stringify(items, null, 2);
        if (items.length === 0) {
             displayElement.textContent = "(Không có dữ liệu)";
        } else {
            displayElement.textContent = items.map(item =>
                `ID: ${item.id}, Name: ${item.name}, Created: ${new Date(item.created_at).toLocaleString()}`
            ).join('\n');
        }
    } catch (error) {
        console.error(`Lỗi khi fetch dữ liệu từ node ${nodeId}:`, error);
        displayElement.textContent = `Lỗi: ${error.message}`;
        displayElement.style.color = 'red';
    }
}

// Hàm fetch dữ liệu cho tất cả các node
function fetchAllData() {
    Object.keys(nodeDisplays).forEach(nodeId => {
        nodeDisplays[nodeId].style.color = 'black'; // Reset màu chữ
        fetchDataForNode(nodeId);
    });
}

// Hàm thêm item mới
async function addItem() {
    const name = itemNameInput.value.trim();
    if (!name) {
        showStatus('Vui lòng nhập tên item!', true);
        return;
    }

    addItemBtn.disabled = true; // Vô hiệu hóa nút trong khi gửi request
    showStatus('Đang thêm item...');

    try {
        const response = await fetch(`${API_BASE_URL}/items`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name: name }),
        });

        const result = await response.json();

        if (!response.ok) {
             throw new Error(result.error || `Lỗi ${response.status}`);
        }

        showStatus(result.message || 'Thêm item thành công!');
        itemNameInput.value = ''; // Xóa input

        
        searchResultsDisplay.textContent = 'Thêm item mới có thể ảnh hưởng kết quả tìm kiếm cũ. Nhấn Tìm để cập nhật.';
        searchResultsDisplay.style.color = 'gray';

        // Quan trọng: Đợi một chút rồi làm mới dữ liệu trên tất cả các node
        // để có thời gian cho eventual consistency hoạt động (mô phỏng)
        setTimeout(fetchAllData, 700); // Chờ 0.7 giây

    } catch (error) {
        console.error('Lỗi khi thêm item:', error);
        showStatus(`Lỗi: ${error.message}`, true);
    } finally {
         addItemBtn.disabled = false; // Kích hoạt lại nút
    }
}

async function searchItems() {
    const searchTerm = searchTermInput.value.trim();
    if (!searchTerm) {
        searchResultsDisplay.textContent = 'Vui lòng nhập nội dung tìm kiếm.';
        searchResultsDisplay.style.color = 'orange';
        return;
    }

    searchBtn.disabled = true;
    searchResultsDisplay.textContent = 'Đang tìm kiếm...';
    searchResultsDisplay.style.color = 'black';

    try {
        // Encode search term để tránh lỗi với ký tự đặc biệt trong URL
        const encodedSearchTerm = encodeURIComponent(searchTerm);
        const response = await fetch(`${API_BASE_URL}/items/search?q=${encodedSearchTerm}`);

        const data = await response.json(); // Đọc body JSON bất kể response.ok

        if (!response.ok) {
            throw new Error(data.error || `Lỗi ${response.status}`);
        }

        // Hiển thị kết quả
        if (data.results && data.results.length > 0) {
             searchResultsDisplay.textContent = data.results.map(item =>
                `ID: ${item.id}, Name: ${item.name}, Created: ${new Date(item.created_at).toLocaleString()} (Found on: ${item.found_on.join(', ')})`
             ).join('\n');
        } else {
             searchResultsDisplay.textContent = 'Không tìm thấy kết quả nào.';
        }

        // (Tùy chọn) Hiển thị cảnh báo nếu có
        if (data.warnings && data.warnings.length > 0) {
            searchResultsDisplay.textContent += '\n\nCảnh báo:\n' + data.warnings.join('\n');
             searchResultsDisplay.style.color = 'orange'; // Đổi màu nếu có cảnh báo
        }

    } catch (error) {
        console.error('Lỗi khi tìm kiếm:', error);
        searchResultsDisplay.textContent = `Lỗi tìm kiếm: ${error.message}`;
        searchResultsDisplay.style.color = 'red';
    } finally {
        searchBtn.disabled = false;
    }
}

// Gắn sự kiện click cho nút "Thêm Item"
addItemBtn.addEventListener('click', addItem);

searchBtn.addEventListener('click', searchItems);


// Gắn sự kiện cho các nút "Làm mới"
refreshButtons.forEach(button => {
    button.addEventListener('click', () => {
        const nodeId = button.getAttribute('data-node');
         nodeDisplays[nodeId].style.color = 'black'; // Reset màu
        fetchDataForNode(nodeId);
    });
});

// Tải dữ liệu lần đầu khi trang được load
document.addEventListener('DOMContentLoaded', fetchAllData);

// (Tùy chọn) Tự động làm mới sau mỗi X giây
// setInterval(fetchAllData, 10000); // Làm mới mỗi 10 giây



