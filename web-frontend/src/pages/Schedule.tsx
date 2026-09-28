import Header from '../components/Header';
import { mockData } from '../data/mockData';
import { Calendar as CalendarIcon, Clock } from 'lucide-react';
import './Dashboard.css';

export default function Schedule() {
  return (
    <div className="dashboard-container">
      <Header />
      <main className="dashboard-main">
        <section className="welcome-section">
          <div className="welcome-text">
            <h1>상담 일정</h1>
            <p className="subtitle">전체 상담 일정을 확인하고 관리하세요.</p>
          </div>
          <button className="btn-primary"><CalendarIcon size={16} /> 새 일정 추가</button>
        </section>

        <div className="dashboard-grid" style={{ gridTemplateColumns: '1fr' }}>
          <div className="card">
            <h2 style={{ marginBottom: '24px', fontSize: '1.25rem', fontWeight: 700 }}>이번 주 일정</h2>
            <div className="schedule-list">
              {mockData.schedules.map(s => (
                <div key={s.id} className="schedule-item" style={{ flexDirection: 'row', alignItems: 'center', padding: '24px' }}>
                  <div style={{ flex: '0 0 120px' }}>
                    <div style={{ fontWeight: 700, fontSize: '1.2rem', marginBottom: '4px' }}>{s.date.split('-')[2]}일</div>
                    <div style={{ color: '#888', display: 'flex', alignItems: 'center', gap: '4px' }}><Clock size={14} /> {s.time}</div>
                  </div>
                  <div className="details" style={{ margin: 0, paddingLeft: '24px', borderLeft: '3px solid var(--primary)' }}>
                    <div className="person">
                      <h4>{s.childName}</h4>
                      <span className="tag blue">{s.type}</span>
                    </div>
                    <p className="desc">{s.desc}</p>
                  </div>
                  <div style={{ marginLeft: 'auto' }}>
                    <button className="btn-outline">일정 변경</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
