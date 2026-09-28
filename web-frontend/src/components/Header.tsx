import { Link, NavLink } from 'react-router-dom';
import { mockData } from '../data/mockData';
import { Home, Users, Calendar, FileText, FileSearch } from 'lucide-react';
import './Header.css';

export default function Header() {
  return (
    <header className="dashboard-header">
      <div className="header-left">
        <Link to="/" className="nav-logo">
          <span className="logo-icon">I</span>
          <span className="logo-text">·SPOT</span>
        </Link>
      </div>
      <nav className="header-nav">
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
          <Home className="nav-icon" size={20} />
          <span>오늘의 업무</span>
        </NavLink>
        <NavLink to="/cases" className={({ isActive }) => isActive ? 'active' : ''}>
          <Users className="nav-icon" size={20} />
          <span>담당 사례</span>
        </NavLink>
        <NavLink to="/schedule" className={({ isActive }) => isActive ? 'active' : ''}>
          <Calendar className="nav-icon" size={20} />
          <span>상담 일정</span>
        </NavLink>
        <NavLink to="/records" className={({ isActive }) => isActive ? 'active' : ''}>
          <FileText className="nav-icon" size={20} />
          <span>상담 기록</span>
        </NavLink>
        <NavLink to="/reviews" className={({ isActive }) => isActive ? 'active' : ''}>
          <FileSearch className="nav-icon" size={20} />
          <span>자료 검토</span>
        </NavLink>
      </nav>
      <div className="header-right">
        <a href="#" className="help-link">도움말</a>
        <div className="user-profile">
          <div className="avatar">{mockData.user.avatar}</div>
          <span className="profile-name">{mockData.user.name}</span>
        </div>
      </div>
    </header>
  );
}
