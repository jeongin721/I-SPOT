import Header from '../components/Header';
import { mockData } from '../data/mockData';
import { FileText, Plus } from 'lucide-react';
import './Dashboard.css';

export default function Records() {
  return (
    <div className="dashboard-container">
      <Header />
      <main className="dashboard-main">
        <section className="welcome-section">
          <div className="welcome-text">
            <h1>상담 기록</h1>
            <p className="subtitle">진행된 상담의 기록을 작성하고 보관합니다.</p>
          </div>
          <button className="btn-primary"><Plus size={16} /> 새 일지 작성</button>
        </section>

        <div className="card">
          <div className="doc-list" style={{ gap: '16px' }}>
            {mockData.records.map(r => (
              <div key={r.id} className="doc-item" style={{ background: '#fafbfc', padding: '20px', borderRadius: '12px' }}>
                <div className="doc-icon" style={{ background: 'white' }}><FileText size={24} /></div>
                <div className="doc-info">
                  <h4 style={{ fontSize: '1.1rem' }}>{r.title}</h4>
                  <p style={{ marginTop: '8px' }}>아동: {r.childName} <span style={{ margin: '0 8px' }}>|</span> 일자: {r.date}</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <span className={`tag ${r.status === '작성 완료' ? 'outline-blue' : 'red'}`}>{r.status}</span>
                  <button className="btn-outline">
                    {r.status === '작성 완료' ? '조회' : '이어서 작성'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
