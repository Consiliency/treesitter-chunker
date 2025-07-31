#!/usr/bin/env node
/**
 * JavaScript/Node.js client for the Tree-sitter Chunker REST API.
 * 
 * Usage:
 *   npm install axios
 *   node client.js
 */

const axios = require('axios');

class ChunkerClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    async healthCheck() {
        const response = await axios.get(`${this.baseUrl}/health`);
        return response.data;
    }

    async listLanguages() {
        const response = await axios.get(`${this.baseUrl}/languages`);
        return response.data;
    }

    async chunkText(content, language, options = {}) {
        const payload = {
            content,
            language,
            ...options
        };
        
        const response = await axios.post(`${this.baseUrl}/chunk/text`, payload);
        return response.data;
    }

    async chunkFile(filePath, options = {}) {
        const payload = {
            file_path: filePath,
            ...options
        };
        
        const response = await axios.post(`${this.baseUrl}/chunk/file`, payload);
        return response.data;
    }
}

// Example usage
async function main() {
    const client = new ChunkerClient();
    
    try {
        // Check health
        const health = await client.healthCheck();
        console.log('Health check:', health);
        
        // List languages
        const languages = await client.listLanguages();
        console.log('\nSupported languages:', languages);
        
        // Example JavaScript code
        const jsCode = `
function fibonacci(n) {
    if (n <= 0) return 0;
    if (n === 1) return 1;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

class Calculator {
    constructor() {
        this.history = [];
    }
    
    add(a, b) {
        const result = a + b;
        this.history.push({ operation: 'add', a, b, result });
        return result;
    }
    
    multiply(a, b) {
        const result = a * b;
        this.history.push({ operation: 'multiply', a, b, result });
        return result;
    }
    
    getHistory() {
        return this.history;
    }
}
`;
        
        // Chunk the code
        const result = await client.chunkText(jsCode, 'javascript', {
            min_chunk_size: 3
        });
        
        console.log(`\nFound ${result.total_chunks} chunks:`);
        result.chunks.forEach((chunk, i) => {
            console.log(`\n${i + 1}. ${chunk.node_type} (lines ${chunk.start_line}-${chunk.end_line})`);
            if (chunk.parent_context) {
                console.log(`   Parent: ${chunk.parent_context}`);
            }
            console.log(`   Size: ${chunk.size} lines`);
            const preview = chunk.content.length > 100 
                ? chunk.content.substring(0, 100) + '...' 
                : chunk.content;
            console.log(`   Content preview: ${preview}`);
        });
        
    } catch (error) {
        console.error('Error:', error.message);
        if (error.response) {
            console.error('Response:', error.response.data);
        }
    }
}

// Run if called directly
if (require.main === module) {
    main();
}

module.exports = ChunkerClient;