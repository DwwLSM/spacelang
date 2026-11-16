const databaseName = "spacelang-opt-sp";
const storeName = "file-handles";

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1);
    request.addEventListener("upgradeneeded", () => {
      request.result.createObjectStore(storeName);
    });
    request.addEventListener("success", () => resolve(request.result), { once: true });
    request.addEventListener("error", () => reject(request.error), { once: true });
  });
}

export async function storeFileHandle(handle) {
  const database = await openDatabase();
  const id = crypto.randomUUID();
  try {
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, "readwrite");
      transaction.objectStore(storeName).put(handle, id);
      transaction.addEventListener("complete", resolve, { once: true });
      transaction.addEventListener("error", () => reject(transaction.error), { once: true });
      transaction.addEventListener("abort", () => reject(transaction.error), { once: true });
    });
    return id;
  } finally {
    database.close();
  }
}

export async function getFileHandle(id) {
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const request = database.transaction(storeName).objectStore(storeName).get(id);
      request.addEventListener("success", () => resolve(request.result ?? null), { once: true });
      request.addEventListener("error", () => reject(request.error), { once: true });
    });
  } finally {
    database.close();
  }
}
