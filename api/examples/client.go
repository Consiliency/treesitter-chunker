package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// ChunkerClient is a client for the Tree-sitter Chunker REST API
type ChunkerClient struct {
	BaseURL string
}

// ChunkRequest represents a request to chunk text
type ChunkRequest struct {
	Content       string   `json:"content"`
	Language      string   `json:"language"`
	MinChunkSize  *int     `json:"min_chunk_size,omitempty"`
	MaxChunkSize  *int     `json:"max_chunk_size,omitempty"`
	ChunkTypes    []string `json:"chunk_types,omitempty"`
}

// ChunkFileRequest represents a request to chunk a file
type ChunkFileRequest struct {
	FilePath      string   `json:"file_path"`
	Language      *string  `json:"language,omitempty"`
	MinChunkSize  *int     `json:"min_chunk_size,omitempty"`
	MaxChunkSize  *int     `json:"max_chunk_size,omitempty"`
	ChunkTypes    []string `json:"chunk_types,omitempty"`
}

// Chunk represents a code chunk
type Chunk struct {
	NodeType      string  `json:"node_type"`
	StartLine     int     `json:"start_line"`
	EndLine       int     `json:"end_line"`
	Content       string  `json:"content"`
	ParentContext *string `json:"parent_context"`
	Size          int     `json:"size"`
}

// ChunkResult represents the result of chunking
type ChunkResult struct {
	Chunks      []Chunk `json:"chunks"`
	TotalChunks int     `json:"total_chunks"`
	Language    string  `json:"language"`
}

// HealthResponse represents the health check response
type HealthResponse struct {
	Status  string `json:"status"`
	Version string `json:"version"`
}

// NewChunkerClient creates a new chunker client
func NewChunkerClient(baseURL string) *ChunkerClient {
	return &ChunkerClient{
		BaseURL: strings.TrimSuffix(baseURL, "/"),
	}
}

// HealthCheck checks if the API is healthy
func (c *ChunkerClient) HealthCheck() (*HealthResponse, error) {
	resp, err := http.Get(c.BaseURL + "/health")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var health HealthResponse
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		return nil, err
	}

	return &health, nil
}

// ListLanguages gets the list of supported languages
func (c *ChunkerClient) ListLanguages() ([]string, error) {
	resp, err := http.Get(c.BaseURL + "/languages")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var languages []string
	if err := json.NewDecoder(resp.Body).Decode(&languages); err != nil {
		return nil, err
	}

	return languages, nil
}

// ChunkText chunks source code text
func (c *ChunkerClient) ChunkText(req ChunkRequest) (*ChunkResult, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(
		c.BaseURL+"/chunk/text",
		"application/json",
		bytes.NewBuffer(data),
	)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error: %s", string(body))
	}

	var result ChunkResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return &result, nil
}

// ChunkFile chunks a source code file
func (c *ChunkerClient) ChunkFile(req ChunkFileRequest) (*ChunkResult, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(
		c.BaseURL+"/chunk/file",
		"application/json",
		bytes.NewBuffer(data),
	)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error: %s", string(body))
	}

	var result ChunkResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return &result, nil
}

func main() {
	// Create client
	client := NewChunkerClient("http://localhost:8000")

	// Check health
	health, err := client.HealthCheck()
	if err != nil {
		fmt.Printf("Health check failed: %v\n", err)
		return
	}
	fmt.Printf("Health check: %+v\n", health)

	// List languages
	languages, err := client.ListLanguages()
	if err != nil {
		fmt.Printf("Failed to list languages: %v\n", err)
		return
	}
	fmt.Printf("\nSupported languages: %v\n", languages)

	// Example Go code
	goCode := `
package main

import "fmt"

func fibonacci(n int) int {
    if n <= 0 {
        return 0
    }
    if n == 1 {
        return 1
    }
    return fibonacci(n-1) + fibonacci(n-2)
}

type Calculator struct {
    history []Operation
}

type Operation struct {
    Type   string
    A, B   float64
    Result float64
}

func (c *Calculator) Add(a, b float64) float64 {
    result := a + b
    c.history = append(c.history, Operation{
        Type:   "add",
        A:      a,
        B:      b,
        Result: result,
    })
    return result
}

func (c *Calculator) Multiply(a, b float64) float64 {
    result := a * b
    c.history = append(c.history, Operation{
        Type:   "multiply",
        A:      a,
        B:      b,
        Result: result,
    })
    return result
}

func (c *Calculator) GetHistory() []Operation {
    return c.history
}
`

	// Chunk the code
	minSize := 3
	result, err := client.ChunkText(ChunkRequest{
		Content:      goCode,
		Language:     "go",
		MinChunkSize: &minSize,
	})
	if err != nil {
		fmt.Printf("Failed to chunk text: %v\n", err)
		return
	}

	fmt.Printf("\nFound %d chunks:\n", result.TotalChunks)
	for i, chunk := range result.Chunks {
		fmt.Printf("\n%d. %s (lines %d-%d)\n", i+1, chunk.NodeType, chunk.StartLine, chunk.EndLine)
		if chunk.ParentContext != nil {
			fmt.Printf("   Parent: %s\n", *chunk.ParentContext)
		}
		fmt.Printf("   Size: %d lines\n", chunk.Size)
		
		// Show content preview
		preview := chunk.Content
		if len(preview) > 100 {
			preview = preview[:100] + "..."
		}
		fmt.Printf("   Content preview: %s\n", preview)
	}
}