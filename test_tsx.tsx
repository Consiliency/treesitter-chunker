import React, { useState, useEffect } from 'react';

interface User {
  id: number;
  name: string;
  email: string;
}

interface UserListProps {
  users: User[];
  onUserSelect: (user: User) => void;
}

const UserList: React.FC<UserListProps> = ({ users, onUserSelect }) => {
  return (
    <div className="user-list">
      {users.map(user => (
        <div 
          key={user.id} 
          className="user-item"
          onClick={() => onUserSelect(user)}
        >
          <h3>{user.name}</h3>
          <p>{user.email}</p>
        </div>
      ))}
    </div>
  );
};

const UserProfile: React.FC<{ user: User | null }> = ({ user }) => {
  if (!user) {
    return <div>No user selected</div>;
  }
  
  return (
    <div className="user-profile">
      <h2>{user.name}</h2>
      <p>Email: {user.email}</p>
      <p>ID: {user.id}</p>
    </div>
  );
};

export const App: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  
  useEffect(() => {
    // Simulate API call
    const fetchUsers = async () => {
      const response = await fetch('/api/users');
      const data = await response.json();
      setUsers(data);
    };
    
    fetchUsers();
  }, []);
  
  return (
    <div className="app">
      <h1>User Management</h1>
      <div className="app-content">
        <UserList users={users} onUserSelect={setSelectedUser} />
        <UserProfile user={selectedUser} />
      </div>
    </div>
  );
};
