<?php
require 'db.php';
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit;
}

// Crear tabla si no existe
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS herramientas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        brand VARCHAR(100),
        model VARCHAR(100),
        color VARCHAR(50),
        category VARCHAR(100),
        other_data TEXT,
        image_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (PDOException $e) {
    // Tabla ya existe, no pasa nada
}

$method = $_SERVER['REQUEST_METHOD'];

try {
    if ($method === 'GET') {
        // Listar todas las herramientas
        $stmt = $pdo->query("SELECT * FROM herramientas ORDER BY created_at DESC");
        $tools = $stmt->fetchAll(PDO::FETCH_ASSOC);
        echo json_encode(['success' => true, 'data' => $tools]);

    } elseif ($method === 'POST') {
        $json = file_get_contents('php://input');
        $data = json_decode($json, true);

        if (!$data) {
            echo json_encode(['success' => false, 'error' => 'No se recibieron datos']);
            exit;
        }

        $stmt = $pdo->prepare("INSERT INTO herramientas (name, brand, model, color, category, image_url, other_data) 
                               VALUES (?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([
            $data['name'] ?? '',
            $data['brand'] ?? '',
            $data['model'] ?? '',
            $data['color'] ?? '',
            $data['category'] ?? '',
            $data['image_url'] ?? '',
            json_encode($data['other'] ?? [], JSON_UNESCAPED_UNICODE)
        ]);

        $id = $pdo->lastInsertId();
        echo json_encode(['success' => true, 'id' => $id]);
    }

} catch (PDOException $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
