"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
function activate(context) {
    console.log('TreeSitter Chunker extension is now active!');
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('treesitter-chunker.chunkFile', () => chunkCurrentFile()), vscode.commands.registerCommand('treesitter-chunker.chunkWorkspace', () => chunkWorkspace()), vscode.commands.registerCommand('treesitter-chunker.showChunks', () => showChunks()), vscode.commands.registerCommand('treesitter-chunker.exportChunks', () => exportChunks()));
    // Create chunk decorator
    const chunkDecorationType = vscode.window.createTextEditorDecorationType({
        borderWidth: '1px',
        borderStyle: 'solid',
        overviewRulerColor: 'blue',
        overviewRulerLane: vscode.OverviewRulerLane.Right,
        light: {
            borderColor: 'darkblue'
        },
        dark: {
            borderColor: 'lightblue'
        }
    });
    // Store chunks for the current session
    const chunksCache = new Map();
    async function chunkCurrentFile() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor found');
            return;
        }
        const document = editor.document;
        const filePath = document.fileName;
        const language = getLanguageFromFile(filePath);
        if (!language) {
            vscode.window.showErrorMessage('Unsupported file type');
            return;
        }
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Chunking file...',
            cancellable: false
        }, async (progress) => {
            try {
                const chunks = await runChunker(filePath, language);
                chunksCache.set(filePath, chunks);
                // Show chunk boundaries if enabled
                const showBoundaries = vscode.workspace.getConfiguration('treesitter-chunker').get('showChunkBoundaries');
                if (showBoundaries) {
                    highlightChunks(editor, chunks, chunkDecorationType);
                }
                vscode.window.showInformationMessage(`Found ${chunks.length} chunks in ${path.basename(filePath)}`);
            }
            catch (error) {
                vscode.window.showErrorMessage(`Error chunking file: ${error}`);
            }
        });
    }
    async function chunkWorkspace() {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }
        const supportedExtensions = ['.py', '.js', '.ts', '.rs', '.c', '.cpp'];
        const files = await vscode.workspace.findFiles(`**/*{${supportedExtensions.join(',')}}`, '**/node_modules/**');
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Chunking workspace...',
            cancellable: true
        }, async (progress, token) => {
            let processed = 0;
            const total = files.length;
            for (const file of files) {
                if (token.isCancellationRequested) {
                    break;
                }
                const language = getLanguageFromFile(file.fsPath);
                if (language) {
                    try {
                        const chunks = await runChunker(file.fsPath, language);
                        chunksCache.set(file.fsPath, chunks);
                        processed++;
                        progress.report({
                            message: `${processed}/${total} files`,
                            increment: 100 / total
                        });
                    }
                    catch (error) {
                        console.error(`Error chunking ${file.fsPath}: ${error}`);
                    }
                }
            }
            vscode.window.showInformationMessage(`Chunked ${processed} files in workspace`);
        });
    }
    async function showChunks() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor found');
            return;
        }
        const filePath = editor.document.fileName;
        const chunks = chunksCache.get(filePath);
        if (!chunks || chunks.length === 0) {
            vscode.window.showInformationMessage('No chunks found. Run "Chunk Current File" first.');
            return;
        }
        const panel = vscode.window.createWebviewPanel('chunkView', `Chunks: ${path.basename(filePath)}`, vscode.ViewColumn.Two, {
            enableScripts: true
        });
        panel.webview.html = getChunkViewHtml(chunks);
    }
    async function exportChunks() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor found');
            return;
        }
        const filePath = editor.document.fileName;
        const chunks = chunksCache.get(filePath);
        if (!chunks || chunks.length === 0) {
            vscode.window.showInformationMessage('No chunks found. Run "Chunk Current File" first.');
            return;
        }
        const format = vscode.workspace.getConfiguration('treesitter-chunker').get('exportFormat');
        const outputPath = await vscode.window.showSaveDialog({
            defaultUri: vscode.Uri.file(filePath.replace(path.extname(filePath), `.chunks.${format}`)),
            filters: {
                'Chunk Files': [format]
            }
        });
        if (outputPath) {
            try {
                await runExport(filePath, outputPath.fsPath, format);
                vscode.window.showInformationMessage(`Exported chunks to ${path.basename(outputPath.fsPath)}`);
            }
            catch (error) {
                vscode.window.showErrorMessage(`Error exporting chunks: ${error}`);
            }
        }
    }
    function runChunker(filePath, language) {
        return new Promise((resolve, reject) => {
            const pythonPath = vscode.workspace.getConfiguration('treesitter-chunker').get('pythonPath');
            const process = (0, child_process_1.spawn)(pythonPath, ['-m', 'chunker.cli', 'chunk', filePath, '-l', language, '--json']);
            let stdout = '';
            let stderr = '';
            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });
            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            process.on('close', (code) => {
                if (code === 0) {
                    try {
                        const chunks = JSON.parse(stdout);
                        resolve(chunks);
                    }
                    catch (error) {
                        reject(`Failed to parse output: ${error}`);
                    }
                }
                else {
                    reject(stderr || `Process exited with code ${code}`);
                }
            });
        });
    }
    function runExport(filePath, outputPath, format) {
        return new Promise((resolve, reject) => {
            const pythonPath = vscode.workspace.getConfiguration('treesitter-chunker').get('pythonPath');
            const process = (0, child_process_1.spawn)(pythonPath, ['-m', 'chunker.cli', 'export', filePath, outputPath, '-f', format]);
            let stderr = '';
            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            process.on('close', (code) => {
                if (code === 0) {
                    resolve();
                }
                else {
                    reject(stderr || `Process exited with code ${code}`);
                }
            });
        });
    }
    function getLanguageFromFile(filePath) {
        const ext = path.extname(filePath).toLowerCase();
        const languageMap = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp'
        };
        return languageMap[ext] || null;
    }
    function highlightChunks(editor, chunks, decorationType) {
        const decorations = chunks.map(chunk => {
            const startPos = editor.document.positionAt(chunk.start_byte);
            const endPos = editor.document.positionAt(chunk.end_byte);
            return {
                range: new vscode.Range(startPos, endPos),
                hoverMessage: `${chunk.node_type} (lines ${chunk.start_line}-${chunk.end_line})`
            };
        });
        editor.setDecorations(decorationType, decorations);
    }
    function getChunkViewHtml(chunks) {
        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Code Chunks</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    padding: 20px;
                }
                .chunk {
                    margin-bottom: 20px;
                    border: 1px solid #ddd;
                    padding: 10px;
                    border-radius: 5px;
                }
                .chunk-header {
                    font-weight: bold;
                    margin-bottom: 10px;
                    color: #0066cc;
                }
                .chunk-info {
                    font-size: 0.9em;
                    color: #666;
                    margin-bottom: 10px;
                }
                pre {
                    background-color: #f5f5f5;
                    padding: 10px;
                    border-radius: 3px;
                    overflow-x: auto;
                }
                code {
                    font-family: Consolas, Monaco, 'Courier New', monospace;
                }
            </style>
        </head>
        <body>
            <h1>Code Chunks (${chunks.length} total)</h1>
            ${chunks.map((chunk, index) => `
                <div class="chunk">
                    <div class="chunk-header">${index + 1}. ${chunk.node_type}</div>
                    <div class="chunk-info">
                        Lines: ${chunk.start_line}-${chunk.end_line} | 
                        ${chunk.parent_context ? `Context: ${chunk.parent_context}` : 'Top-level'}
                    </div>
                    <pre><code>${escapeHtml(chunk.content)}</code></pre>
                </div>
            `).join('')}
        </body>
        </html>`;
    }
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}
exports.activate = activate;
function deactivate() { }
exports.deactivate = deactivate;
//# sourceMappingURL=extension.js.map