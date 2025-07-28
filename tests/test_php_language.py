"""Test PHP language support."""

import pytest

from chunker import chunk_text
from chunker.languages import language_config_registry


class TestPHPLanguage:
    """Test PHP language chunking."""

    def test_php_basic_chunking(self):
        """Test basic PHP chunking."""
        code = '''<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Support\\Facades\\Hash;

class User extends Model
{
    protected $fillable = ['name', 'email', 'password'];
    
    public function setPasswordAttribute($value)
    {
        $this->attributes['password'] = Hash::make($value);
    }
    
    public function posts()
    {
        return $this->hasMany(Post::class);
    }
    
    public static function findByEmail($email)
    {
        return static::where('email', $email)->first();
    }
}

function validateEmail($email) {
    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
}

trait HasTimestamps {
    public function touch() {
        $this->updated_at = now();
        return $this->save();
    }
}
?>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 5  # class with methods, function, trait
        
        # Verify chunk types
        chunk_contents = [chunk.content for chunk in chunks]
        assert any("class User" in c for c in chunk_contents)
        assert any("function validateEmail" in c for c in chunk_contents)
        assert any("trait HasTimestamps" in c for c in chunk_contents)

    def test_php_interface_abstract(self):
        """Test PHP interfaces and abstract classes."""
        code = '''<?php
interface PaymentGateway {
    public function charge($amount);
    public function refund($transactionId, $amount);
}

abstract class BaseController {
    protected $request;
    
    abstract protected function authorize();
    
    public function handle() {
        if (!$this->authorize()) {
            throw new UnauthorizedException();
        }
        return $this->process();
    }
    
    protected function process() {
        return response()->json(['status' => 'ok']);
    }
}
?>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 2  # interface and abstract class

    def test_php_anonymous_functions(self):
        """Test PHP anonymous functions and closures."""
        code = '''<?php
$users = [
    ['name' => 'John', 'age' => 30],
    ['name' => 'Jane', 'age' => 25],
];

$adults = array_filter($users, function($user) {
    return $user['age'] >= 18;
});

$multiplier = 10;
$calculate = function($number) use ($multiplier) {
    return $number * $multiplier;
};

class EventEmitter {
    private $listeners = [];
    
    public function on($event, callable $callback) {
        $this->listeners[$event][] = $callback;
    }
    
    public function emit($event, $data = null) {
        foreach ($this->listeners[$event] ?? [] as $callback) {
            $callback($data);
        }
    }
}
?>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 1  # class with methods

    def test_php_modern_syntax(self):
        """Test modern PHP syntax features."""
        code = '''<?php
declare(strict_types=1);

namespace App\\Services;

use App\\Contracts\\{ServiceInterface, LoggerInterface};

readonly class Configuration {
    public function __construct(
        private string $appName,
        private string $version,
        private array $settings = []
    ) {}
}

enum Status: string {
    case PENDING = 'pending';
    case APPROVED = 'approved';
    case REJECTED = 'rejected';
    
    public function getLabel(): string {
        return match($this) {
            self::PENDING => 'Awaiting Review',
            self::APPROVED => 'Approved',
            self::REJECTED => 'Rejected',
        };
    }
}

#[Route('/api/users', methods: ['GET'])]
class UserController {
    public function __construct(
        private UserRepository $users,
        private ?LoggerInterface $logger = null
    ) {}
    
    public function index(): JsonResponse {
        return response()->json(
            $this->users->all()
        );
    }
}
?>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 3  # multiple classes and enum

    def test_php_mixed_content(self):
        """Test PHP with mixed HTML content."""
        code = '''<!DOCTYPE html>
<html>
<head>
    <title><?php echo $title; ?></title>
</head>
<body>
    <?php
    class TemplateEngine {
        private $vars = [];
        
        public function assign($key, $value) {
            $this->vars[$key] = $value;
        }
        
        public function render($template) {
            extract($this->vars);
            include $template;
        }
    }
    
    function formatDate($date) {
        return date('Y-m-d', strtotime($date));
    }
    ?>
    
    <div class="content">
        <?php foreach ($items as $item): ?>
            <div><?= htmlspecialchars($item) ?></div>
        <?php endforeach; ?>
    </div>
</body>
</html>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 2  # class and function

    def test_php_namespace_use(self):
        """Test PHP namespace and use statements."""
        code = '''<?php
namespace App\\Http\\Controllers\\Api\\V1;

use App\\Models\\{User, Post, Comment};
use App\\Services\\NotificationService;
use Illuminate\\Http\\{Request, JsonResponse};
use Illuminate\\Support\\Facades\\{Cache, Log};

class PostController extends Controller
{
    use HasApiTokens, Notifiable;
    
    public function __construct(
        private NotificationService $notifications
    ) {
        $this->middleware('auth:api');
    }
    
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'content' => 'required|string',
        ]);
        
        $post = Post::create($validated);
        
        $this->notifications->notifyFollowers($post);
        
        return response()->json($post, 201);
    }
}
?>'''
        chunks = chunk_text(code, language="php")
        assert len(chunks) >= 1  # class with constructor and method

    @pytest.mark.parametrize("file_extension", [".php", ".php3", ".php4", ".php5", ".phtml"])
    def test_php_file_extensions(self, file_extension):
        """Test PHP file extension detection."""
        config = language_config_registry.get_for_file(f"test{file_extension}")
        assert config is not None
        assert config.name == "php"