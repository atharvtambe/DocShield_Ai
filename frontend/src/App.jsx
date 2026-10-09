import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  MessageSquare,
  Shield,
  Activity,
  Award,
  Layers,
  Building,
  TrendingUp,
  FileCheck,
  Send,
  Download,
  Printer,
  Sparkles,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Database
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [health, setHealth] = useState(null);
  const [tenders, setTenders] = useState([]);
  const [selectedTenderId, setSelectedTenderId] = useState(null);
  const [selectedTender, setSelectedTender] = useState(null);
  
  // Requirements state
  const [requirements, setRequirements] = useState({ items: [], category_counts: {}, total: 0 });
  const [reqCategoryFilter, setReqCategoryFilter] = useState('ALL');
  const [reqSearch, setReqSearch] = useState('');

  // Compliance state
  const [compliance, setCompliance] = useState(null);
  const [loadingCompliance, setLoadingCompliance] = useState(false);

  // Profile state
  const [profile, setProfile] = useState({
    company_name: 'AlphaTech Solutions Pvt Ltd',
    turnover_cr: 18.5,
    experience_years: 7.0,
    certifications: ['ISO 9001', 'ISO 27001', 'CMMI Level 3'],
    technical_capabilities: ['Cloud Architecture', 'Kubernetes', 'AI / Computer Vision', 'PostgreSQL'],
    location: 'Bangalore, India',
    employee_count: 85
  });
  const [profileSavedMsg, setProfileSavedMsg] = useState(false);

  // Chat state
  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'assistant',
      text: 'Hello! I am TenderSense AI. Ask any question about the uploaded tender clauses, mandatory criteria, SLA timelines, or penalties.',
      citations: [],
      confidence: 'HIGH'
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Report state
  const [reportMarkdown, setReportMarkdown] = useState('');

  // Evaluation state
  const [evalResult, setEvalResult] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');

  // Fetch initial data
  useEffect(() => {
    fetchHealth();
    fetchTenders();
    fetchProfile();
  }, []);

  useEffect(() => {
    if (selectedTenderId) {
      fetchTenderDetail(selectedTenderId);
      fetchRequirements(selectedTenderId);
    }
  }, [selectedTenderId]);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health');
      if (res.ok) setHealth(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTenders = async () => {
    try {
      const res = await fetch('/api/tenders');
      if (res.ok) {
        const list = await res.json();
        setTenders(list);
        if (list.length > 0 && !selectedTenderId) {
          setSelectedTenderId(list[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTenderDetail = async (id) => {
    try {
      const res = await fetch(`/api/tenders/${id}`);
      if (res.ok) setSelectedTender(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRequirements = async (id) => {
    try {
      const res = await fetch(`/api/tenders/${id}/requirements`);
      if (res.ok) setRequirements(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchProfile = async () => {
    try {
      const res = await fetch('/api/profile');
      if (res.ok) setProfile(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus('Uploading and parsing pages...');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/tenders/upload', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Uploaded: ${data.title} (${data.pages} pages, ${data.chunks} chunks)`);
        await fetchTenders();
        setSelectedTenderId(data.id);
      } else {
        const err = await res.json();
        setUploadStatus(`Upload failed: ${err.detail || 'Error'}`);
      }
    } catch (err) {
      setUploadStatus(`Error: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = async (type = 'smart_city') => {
    setIsUploading(true);
    setUploadStatus(`Loading sample ${type} RFP...`);
    try {
      const res = await fetch(`/api/tenders/sample/load?sample_type=${type}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Loaded: ${data.title}`);
        await fetchTenders();
        setSelectedTenderId(data.id);
      }
    } catch (e) {
      setUploadStatus(`Error: ${e.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunCompliance = async () => {
    if (!selectedTenderId) return;
    setLoadingCompliance(true);
    try {
      const res = await fetch(`/api/tenders/${selectedTenderId}/compliance`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setCompliance(data);
        setActiveTab('compliance');
        await fetchTenders();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingCompliance(false);
    }
  };

  const handleSendMessage = async (queryText = null) => {
    const q = queryText || inputQuery;
    if (!q.trim() || !selectedTenderId) return;

    const userMsg = { sender: 'user', text: q };
    setChatMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInputQuery('');
    setIsChatLoading(true);

    try {
      const res = await fetch(`/api/tenders/${selectedTenderId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: selectedTenderId,
          question: q,
          include_citations: true
        })
      });

      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [
          ...prev,
          {
            sender: 'assistant',
            text: data.answer,
            citations: data.citations || [],
            confidence: data.confidence,
            guardrail: data.guardrail_status,
            latency_ms: data.latency_ms
          }
        ]);
      }
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: `Error fetching response: ${e.message}`, citations: [] }
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile)
      });
      if (res.ok) {
        setProfileSavedMsg(true);
        setTimeout(() => setProfileSavedMsg(false), 3000);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleLoadReport = async () => {
    if (!selectedTenderId) return;
    try {
      const res = await fetch(`/api/tenders/${selectedTenderId}/report?format=markdown`);
      if (res.ok) {
        const text = await res.text();
        setReportMarkdown(text);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunEvaluation = async () => {
    if (!selectedTenderId) return;
    setEvalLoading(true);
    try {
      const res = await fetch(`/api/evaluation/run?tender_id=${selectedTenderId}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setEvalResult(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setEvalLoading(false);
    }
  };

  const filteredRequirements = requirements.items.filter((item) => {
    const matchesCat = reqCategoryFilter === 'ALL' || item.category === reqCategoryFilter;
    const matchesSearch =
      !reqSearch ||
      item.description.toLowerCase().includes(reqSearch.toLowerCase()) ||
      item.value.toLowerCase().includes(reqSearch.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-area">
          <Shield style={{ color: '#2563eb' }} size={28} />
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: '700', lineHeight: 1.2 }}>TenderSense AI</h1>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Agentic Tender & Compliance Intelligence Platform
            </p>
          </div>
        </div>

        {/* Center / Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {health && (
            <div className="badge badge-neutral" style={{ padding: '6px 12px' }}>
              <Activity size={14} style={{ color: health.cloud_llm_active ? '#16a34a' : '#d97706' }} />
              <span>{health.llm_provider}</span>
            </div>
          )}

          {tenders.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Active RFP:</span>
              <select
                value={selectedTenderId || ''}
                onChange={(e) => setSelectedTenderId(e.target.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border)',
                  maxWidth: '260px'
                }}
              >
                {tenders.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </header>

      {/* Tabs */}
      <nav className="nav-tabs">
        <button
          className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <Layers size={16} /> Dashboard
        </button>
        <button
          className={`tab-btn ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => setActiveTab('analysis')}
        >
          <TrendingUp size={16} /> Tender Analysis
        </button>
        <button
          className={`tab-btn ${activeTab === 'requirements' ? 'active' : ''}`}
          onClick={() => setActiveTab('requirements')}
        >
          <FileCheck size={16} /> Requirement Detail
        </button>
        <button
          className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <MessageSquare size={16} /> AI Evidence Chat
        </button>
        <button
          className={`tab-btn ${activeTab === 'compliance' ? 'active' : ''}`}
          onClick={() => setActiveTab('compliance')}
        >
          <Award size={16} /> Compliance Matrix
        </button>
        <button
          className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          <Building size={16} /> Company Profile
        </button>
        <button
          className={`tab-btn ${activeTab === 'report' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('report');
            handleLoadReport();
          }}
        >
          <FileText size={16} /> Executive Report
        </button>
        <button
          className={`tab-btn ${activeTab === 'evaluation' ? 'active' : ''}`}
          onClick={() => setActiveTab('evaluation')}
        >
          <Sparkles size={16} /> AI Evaluation Suite
        </button>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        {/* ========================================================
            TAB 1: DASHBOARD
        ======================================================== */}
        {activeTab === 'dashboard' && (
          <div>
            {/* Top quick banner */}
            <div
              style={{
                background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)',
                color: 'white',
                padding: '28px',
                borderRadius: '12px',
                marginBottom: '24px'
              }}
            >
              <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '8px' }}>
                Evidence-Backed Tender & Bid Intelligence
              </h2>
              <p style={{ maxWidth: '800px', opacity: 0.9, marginBottom: '20px', fontSize: '14px' }}>
                Upload government or enterprise tender documents (PDF/DOCX) to automatically extract mandatory
                qualifications, perform hybrid RAG retrieval, assess bid readiness against company capabilities, and
                verify provenance with LangGraph guardrails.
              </p>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <label className="btn" style={{ background: 'white', color: '#1e40af', fontWeight: '600' }}>
                  <Upload size={16} /> Upload Tender RFP (PDF/DOCX)
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.txt"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                  />
                </label>
                <button
                  className="btn"
                  style={{ background: 'rgba(255,255,255,0.2)', color: 'white' }}
                  onClick={() => handleLoadSample('smart_city')}
                >
                  ⚡ 1-Click Load Smart City RFP (PDF)
                </button>
                <button
                  className="btn"
                  style={{ background: 'rgba(255,255,255,0.2)', color: 'white' }}
                  onClick={() => handleLoadSample('highway')}
                >
                  ⚡ 1-Click Load Highway RFP (DOCX)
                </button>
              </div>
              {uploadStatus && (
                <div style={{ marginTop: '12px', fontSize: '13px', background: 'rgba(0,0,0,0.2)', padding: '6px 12px', borderRadius: '4px' }}>
                  {uploadStatus}
                </div>
              )}
            </div>

            {/* Current Active Tender Summary */}
            {selectedTender && (
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div>
                    <span className="badge badge-info" style={{ marginBottom: '6px' }}>
                      ACTIVE DOCUMENT
                    </span>
                    <h3 style={{ fontSize: '20px', fontWeight: '700' }}>{selectedTender.title}</h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                      File: {selectedTender.filename} • {selectedTender.page_count} Pages • {selectedTender.chunk_count} Chunks
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn btn-primary"
                      onClick={handleRunCompliance}
                      disabled={loadingCompliance}
                    >
                      <Award size={16} /> {loadingCompliance ? 'Evaluating...' : 'Evaluate Bid Readiness'}
                    </button>
                    <button
                      className="btn btn-outline"
                      onClick={() => setActiveTab('chat')}
                    >
                      <MessageSquare size={16} /> Ask AI
                    </button>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid-4" style={{ marginTop: '16px' }}>
                  <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Requirements</div>
                    <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--primary)' }}>
                      {requirements.total || selectedTender.requirements_count || 0}
                    </div>
                    <div style={{ fontSize: '12px', color: '#16a34a' }}>Structured & Normalized</div>
                  </div>
                  <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Mandatory Clauses</div>
                    <div style={{ fontSize: '28px', fontWeight: '700', color: '#dc2626' }}>
                      {requirements.mandatory_count || 0}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Critical Pre-requisites</div>
                  </div>
                  <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Bid Readiness Score</div>
                    <div style={{ fontSize: '28px', fontWeight: '700', color: '#16a34a' }}>
                      {compliance ? `${compliance.readiness_score}%` : 'Pending'}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {compliance ? compliance.overall_status : 'Click Evaluate'}
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Sections Covered</div>
                    <div style={{ fontSize: '28px', fontWeight: '700', color: '#0284c7' }}>
                      {selectedTender.sections ? selectedTender.sections.length : 4}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Section-Aware Chunks</div>
                  </div>
                </div>
              </div>
            )}

            {/* Recent Uploaded Tenders */}
            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
                Indexed Tenders In Database
              </h3>
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Document Title</th>
                      <th>Format</th>
                      <th>Pages</th>
                      <th>Chunks</th>
                      <th>Extracted Reqs</th>
                      <th>Readiness Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenders.map((t) => (
                      <tr key={t.id} style={{ background: t.id === selectedTenderId ? '#f0f9ff' : 'transparent' }}>
                        <td style={{ fontWeight: '600' }}>{t.title}</td>
                        <td>
                          <span className="badge badge-neutral">{t.file_type.toUpperCase()}</span>
                        </td>
                        <td>{t.page_count}</td>
                        <td>{t.chunk_count}</td>
                        <td>{t.requirements_count}</td>
                        <td>
                          {t.readiness_score !== null ? (
                            <span
                              className={`badge ${
                                t.overall_status === 'QUALIFIED'
                                  ? 'badge-success'
                                  : t.overall_status === 'DISQUALIFIED'
                                  ? 'badge-danger'
                                  : 'badge-warning'
                              }`}
                            >
                              {t.overall_status} ({t.readiness_score}%)
                            </span>
                          ) : (
                            <span className="badge badge-neutral">Not Run</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => setSelectedTenderId(t.id)}
                            style={{ marginRight: '6px' }}
                          >
                            Select
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 2: TENDER ANALYSIS
        ======================================================== */}
        {activeTab === 'analysis' && (
          <div>
            <div className="card">
              <h2 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '8px' }}>
                Tender Requirement Distribution & Scope
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '20px' }}>
                Analysis of extracted requirements categorized into Eligibility, Financial, Technical, Certifications,
                Documentation, Delivery, and Evaluation clauses.
              </p>

              {/* Category Cards */}
              <div className="grid-3" style={{ marginBottom: '24px' }}>
                {Object.entries(requirements.category_counts || {}).map(([cat, count]) => (
                  <div
                    key={cat}
                    style={{
                      padding: '16px',
                      borderRadius: '8px',
                      border: '1px solid var(--border)',
                      background: '#ffffff',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: '500' }}>
                        {cat}
                      </div>
                      <div style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-main)' }}>
                        {count} clauses
                      </div>
                    </div>
                    <span className="badge badge-info">{Math.round((count / (requirements.total || 1)) * 100)}%</span>
                  </div>
                ))}
              </div>

              {/* Mandatory vs Optional Breakdown */}
              <div
                style={{
                  padding: '20px',
                  background: '#f8fafc',
                  borderRadius: '8px',
                  border: '1px solid var(--border)'
                }}
              >
                <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px' }}>
                  Clause Criticality Ratio
                </h4>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '12px' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '13px', fontWeight: '500' }}>Mandatory Clauses</span>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: '#dc2626' }}>
                        {requirements.mandatory_count} ({Math.round((requirements.mandatory_count / (requirements.total || 1)) * 100)}%)
                      </span>
                    </div>
                    <div style={{ height: '8px', background: '#fee2e2', borderRadius: '4px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${(requirements.mandatory_count / (requirements.total || 1)) * 100}%`,
                          background: '#dc2626'
                        }}
                      />
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '13px', fontWeight: '500' }}>Optional / Discretionary</span>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: '#16a34a' }}>
                        {requirements.optional_count} ({Math.round((requirements.optional_count / (requirements.total || 1)) * 100)}%)
                      </span>
                    </div>
                    <div style={{ height: '8px', background: '#dcfce7', borderRadius: '4px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${(requirements.optional_count / (requirements.total || 1)) * 100}%`,
                          background: '#16a34a'
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 3: REQUIREMENT DETAIL
        ======================================================== */}
        {activeTab === 'requirements' && (
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Extracted Requirements & Provenance</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Showing {filteredRequirements.length} requirements with page citations and evidence snippets.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <input
                    type="text"
                    placeholder="Search clause or keyword..."
                    value={reqSearch}
                    onChange={(e) => setReqSearch(e.target.value)}
                    style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px', width: '220px' }}
                  />
                  <select
                    value={reqCategoryFilter}
                    onChange={(e) => setReqCategoryFilter(e.target.value)}
                    style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                  >
                    <option value="ALL">All Categories</option>
                    {Object.keys(requirements.category_counts || {}).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Requirement Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {filteredRequirements.map((r, idx) => (
                  <div
                    key={r.id || idx}
                    style={{
                      padding: '16px',
                      borderRadius: '8px',
                      border: '1px solid var(--border)',
                      background: '#ffffff',
                      boxShadow: 'var(--shadow)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span className="badge badge-info">{r.category}</span>
                        {r.mandatory ? (
                          <span className="badge badge-danger">Mandatory</span>
                        ) : (
                          <span className="badge badge-success">Optional</span>
                        )}
                        <span className="badge badge-neutral">Page {r.page}</span>
                      </div>
                      <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                        Confidence: {r.confidence.toUpperCase()}
                      </span>
                    </div>

                    <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '6px' }}>
                      {r.description}
                    </h4>

                    {r.value && (
                      <div style={{ fontSize: '13px', color: 'var(--text-main)', marginBottom: '8px' }}>
                        <strong>Required Value / Target:</strong>{' '}
                        <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>
                          {r.value}
                        </code>
                      </div>
                    )}

                    {r.raw_quote && (
                      <blockquote
                        style={{
                          fontSize: '13px',
                          color: 'var(--text-muted)',
                          background: '#f8fafc',
                          padding: '10px 14px',
                          borderLeft: '3px solid var(--primary)',
                          borderRadius: '4px'
                        }}
                      >
                        {r.raw_quote}
                      </blockquote>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 4: AI EVIDENCE CHAT
        ======================================================== */}
        {activeTab === 'chat' && (
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Evidence-Backed AI Chat</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Powered by LangGraph Agentic Workflow: Router → Hybrid Retrieval (Chroma + BM25) → Evidence Validator → Guardrails.
                  </p>
                </div>
              </div>

              {/* Sample Quick Questions */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {[
                  'What is the minimum annual turnover required?',
                  'How many years of experience are required?',
                  'Which ISO certifications are mandatory?',
                  'What is the EMD and PBG amount?',
                  'What is the penalty for delivery delays?'
                ].map((q, idx) => (
                  <button
                    key={idx}
                    className="btn btn-outline btn-sm"
                    onClick={() => handleSendMessage(q)}
                    style={{ fontSize: '12px' }}
                  >
                    💬 {q}
                  </button>
                ))}
              </div>

              {/* Chat Messages Box */}
              <div className="chat-box">
                <div className="chat-messages">
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`message-bubble ${msg.sender}`}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>

                      {/* Citations block */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(0,0,0,0.1)' }}>
                          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px' }}>
                            📌 Document Provenance Citations:
                          </div>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            {msg.citations.map((c, cIdx) => (
                              <span
                                key={cIdx}
                                className="badge badge-neutral"
                                style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '11px' }}
                                title={c.snippet}
                              >
                                Page {c.page} • {c.section}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Guardrail badge */}
                      {msg.guardrail && (
                        <div style={{ marginTop: '6px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <span
                            className={`badge ${
                              msg.guardrail === 'APPROVED' ? 'badge-success' : 'badge-warning'
                            }`}
                            style={{ fontSize: '10px' }}
                          >
                            Guardrail: {msg.guardrail}
                          </span>
                          {msg.latency_ms && (
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                              ⚡ {msg.latency_ms} ms
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="message-bubble assistant">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <RefreshCw size={14} className="spin" /> Searching hybrid index & validating evidence...
                      </div>
                    </div>
                  )}
                </div>

                <div className="chat-input-area">
                  <input
                    type="text"
                    className="chat-input"
                    placeholder="Ask any question about tender clauses, qualifications, or SLAs..."
                    value={inputQuery}
                    onChange={(e) => setInputQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  />
                  <button className="btn btn-primary" onClick={() => handleSendMessage()} disabled={isChatLoading}>
                    <Send size={16} /> Send
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 5: COMPLIANCE MATRIX
        ======================================================== */}
        {activeTab === 'compliance' && (
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Compliance & Bid-Readiness Assessment</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Comparing tender criteria against company profile: <strong>{profile.company_name}</strong>
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleRunCompliance}
                  disabled={loadingCompliance}
                >
                  <RefreshCw size={16} /> Re-evaluate Compliance
                </button>
              </div>

              {compliance ? (
                <div>
                  {/* Readiness Banner */}
                  <div
                    style={{
                      padding: '20px',
                      borderRadius: '8px',
                      marginBottom: '20px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background:
                        compliance.overall_status === 'QUALIFIED'
                          ? '#f0fdf4'
                          : compliance.overall_status === 'DISQUALIFIED'
                          ? '#fef2f2'
                          : '#fffbeb',
                      border: `1px solid ${
                        compliance.overall_status === 'QUALIFIED'
                          ? '#bbf7d0'
                          : compliance.overall_status === 'DISQUALIFIED'
                          ? '#fecaca'
                          : '#fde68a'
                      }`
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', textTransform: 'uppercase' }}>
                        Decision Support Recommendation
                      </div>
                      <h3 style={{ fontSize: '22px', fontWeight: '700', margin: '4px 0' }}>
                        Verdict: {compliance.overall_status}
                      </h3>
                      <p style={{ fontSize: '14px', maxWidth: '750px' }}>{compliance.summary_text}</p>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Readiness Score</div>
                      <div style={{ fontSize: '36px', fontWeight: '800', color: 'var(--primary)' }}>
                        {compliance.readiness_score}%
                      </div>
                    </div>
                  </div>

                  {/* Summary Counters */}
                  <div className="grid-4" style={{ marginBottom: '24px' }}>
                    <div style={{ padding: '12px', background: '#f0fdf4', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '12px', color: '#16a34a' }}>Satisfied Clauses</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: '#16a34a' }}>
                        {compliance.satisfied_count}
                      </div>
                    </div>
                    <div style={{ padding: '12px', background: '#fef2f2', borderRadius: '6px', border: '1px solid #fecaca' }}>
                      <div style={{ fontSize: '12px', color: '#dc2626' }}>Failed / Missing</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: '#dc2626' }}>
                        {compliance.missing_count}
                      </div>
                    </div>
                    <div style={{ padding: '12px', background: '#fffbeb', borderRadius: '6px', border: '1px solid #fde68a' }}>
                      <div style={{ fontSize: '12px', color: '#d97706' }}>Risky / Borderline</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: '#d97706' }}>
                        {compliance.risky_count}
                      </div>
                    </div>
                    <div style={{ padding: '12px', background: '#f0f9ff', borderRadius: '6px', border: '1px solid #bae6fd' }}>
                      <div style={{ fontSize: '12px', color: '#0284c7' }}>Clarifications Needed</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: '#0284c7' }}>
                        {compliance.clarification_count}
                      </div>
                    </div>
                  </div>

                  {/* Matrix Table */}
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Status</th>
                          <th>Category</th>
                          <th>Requirement Clause</th>
                          <th>Required Value</th>
                          <th>Company Profile</th>
                          <th>Impact / Reason</th>
                          <th>Page</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compliance.items.map((it, idx) => (
                          <tr key={idx}>
                            <td>
                              <span
                                className={`badge ${
                                  it.status === 'SATISFIED'
                                    ? 'badge-success'
                                    : it.status === 'MISSING'
                                    ? 'badge-danger'
                                    : it.status === 'RISKY'
                                    ? 'badge-warning'
                                    : 'badge-info'
                                }`}
                              >
                                {it.status}
                              </span>
                            </td>
                            <td><strong>{it.category}</strong></td>
                            <td>{it.requirement_text}</td>
                            <td><code>{it.required_value}</code></td>
                            <td><code>{it.company_value}</code></td>
                            <td style={{ fontSize: '13px' }}>{it.reason}</td>
                            <td>Page {it.page}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <Award size={48} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
                  <h3>No Compliance Evaluation Run Yet</h3>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>
                    Click below to compare your company profile against all extracted requirements.
                  </p>
                  <button className="btn btn-primary" onClick={handleRunCompliance}>
                    Run Compliance Check Now
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 6: COMPANY PROFILE
        ======================================================== */}
        {activeTab === 'profile' && (
          <div>
            <div className="card">
              <h2 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '8px' }}>
                Bidding Entity Profile
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '20px' }}>
                Configure company financial parameters, experience, certifications, and capabilities used by the compliance engine.
              </p>

              {profileSavedMsg && (
                <div className="badge badge-success" style={{ marginBottom: '16px', padding: '8px 16px' }}>
                  Profile updated successfully!
                </div>
              )}

              <form onSubmit={handleSaveProfile}>
                <div className="grid-2" style={{ marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                      Company Legal Name
                    </label>
                    <input
                      type="text"
                      value={profile.company_name}
                      onChange={(e) => setProfile({ ...profile, company_name: e.target.value })}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                      Registered Location / Country
                    </label>
                    <input
                      type="text"
                      value={profile.location || ''}
                      onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                    />
                  </div>
                </div>

                <div className="grid-2" style={{ marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                      Annual Average Turnover (₹ in Crores)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={profile.turnover_cr}
                      onChange={(e) => setProfile({ ...profile, turnover_cr: parseFloat(e.target.value) || 0 })}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                      Years of Domain Experience
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      value={profile.experience_years}
                      onChange={(e) => setProfile({ ...profile, experience_years: parseFloat(e.target.value) || 0 })}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                    Held Certifications (comma separated)
                  </label>
                  <input
                    type="text"
                    value={profile.certifications.join(', ')}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        certifications: e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                      })
                    }
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                  />
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '4px' }}>
                    Technical Capabilities & Specializations (comma separated)
                  </label>
                  <input
                    type="text"
                    value={profile.technical_capabilities.join(', ')}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        technical_capabilities: e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                      })
                    }
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px' }}
                  />
                </div>

                <button type="submit" className="btn btn-primary">
                  Save Company Profile
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 7: EXECUTIVE REPORT
        ======================================================== */}
        {activeTab === 'report' && (
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Executive Bid-Readiness Report</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Comprehensive tender summary, gap analysis, and pre-bid recommendation.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <a
                    href={`/api/tenders/${selectedTenderId}/report?format=html`}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-outline"
                  >
                    <Printer size={16} /> Print / Save as PDF
                  </a>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      navigator.clipboard.writeText(reportMarkdown);
                      alert('Markdown copied to clipboard!');
                    }}
                  >
                    <Download size={16} /> Copy Markdown
                  </button>
                </div>
              </div>

              <div
                style={{
                  background: '#f8fafc',
                  border: '1px solid var(--border)',
                  padding: '24px',
                  borderRadius: '8px',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '13px',
                  maxHeight: '600px',
                  overflowY: 'auto'
                }}
              >
                {reportMarkdown || 'Loading report...'}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            TAB 8: EVALUATION SUITE
        ======================================================== */}
        {activeTab === 'evaluation' && (
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Automated AI Evaluation Suite</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    Benchmarks Retrieval Recall, Answer Accuracy, Citation Accuracy, Hallucination Rate, and Latency against 12 ground-truth test questions.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleRunEvaluation}
                  disabled={evalLoading}
                >
                  <Sparkles size={16} /> {evalLoading ? 'Running Suite...' : 'Run Benchmark Evaluation'}
                </button>
              </div>

              {evalResult ? (
                <div>
                  {/* Metric Cards */}
                  <div className="grid-4" style={{ marginBottom: '24px' }}>
                    <div style={{ padding: '16px', background: '#f0fdf4', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '12px', color: '#16a34a' }}>Retrieval Recall</div>
                      <div style={{ fontSize: '28px', fontWeight: '700', color: '#16a34a' }}>
                        {evalResult.retrieval_recall_pct}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Ground truth chunk in top-k</div>
                    </div>

                    <div style={{ padding: '16px', background: '#eff6ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                      <div style={{ fontSize: '12px', color: '#2563eb' }}>Answer Accuracy</div>
                      <div style={{ fontSize: '28px', fontWeight: '700', color: '#2563eb' }}>
                        {evalResult.answer_accuracy_pct}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Semantic & keyword overlap</div>
                    </div>

                    <div style={{ padding: '16px', background: '#faf5ff', borderRadius: '8px', border: '1px solid #e9d5ff' }}>
                      <div style={{ fontSize: '12px', color: '#9333ea' }}>Citation Accuracy</div>
                      <div style={{ fontSize: '28px', fontWeight: '700', color: '#9333ea' }}>
                        {evalResult.citation_accuracy_pct}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Correct page provenance</div>
                    </div>

                    <div style={{ padding: '16px', background: '#fef2f2', borderRadius: '8px', border: '1px solid #fecaca' }}>
                      <div style={{ fontSize: '12px', color: '#dc2626' }}>Hallucination Rate</div>
                      <div style={{ fontSize: '28px', fontWeight: '700', color: '#dc2626' }}>
                        {evalResult.hallucination_rate_pct}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Unsupported claims (lower is better)</div>
                    </div>
                  </div>

                  {/* Benchmark Query Table */}
                  <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px' }}>
                    Per-Question Benchmark Audit ({evalResult.total_questions} Questions)
                  </h4>
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Category</th>
                          <th>Benchmark Query</th>
                          <th>Expected Page</th>
                          <th>Cited Pages</th>
                          <th>Score</th>
                          <th>Guardrail</th>
                          <th>Latency</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evalResult.detailed_results.map((r) => (
                          <tr key={r.id}>
                            <td><span className="badge badge-info">{r.category}</span></td>
                            <td style={{ fontWeight: '500' }}>{r.question}</td>
                            <td>{r.expected_page ? `Page ${r.expected_page}` : 'N/A (Neg)'}</td>
                            <td>{r.cited_pages && r.cited_pages.length > 0 ? r.cited_pages.join(', ') : 'None'}</td>
                            <td>
                              <span className={`badge ${r.accuracy_score >= 0.7 ? 'badge-success' : 'badge-warning'}`}>
                                {Math.round(r.accuracy_score * 100)}%
                              </span>
                            </td>
                            <td>
                              <span className={`badge ${r.guardrail_status === 'APPROVED' ? 'badge-success' : 'badge-warning'}`}>
                                {r.guardrail_status}
                              </span>
                            </td>
                            <td>{r.latency_ms} ms</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <Sparkles size={48} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
                  <h3>Run Automated Evaluation</h3>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>
                    Measures system accuracy, citations, and hallucination resistance against the benchmark suite.
                  </p>
                  <button className="btn btn-primary" onClick={handleRunEvaluation}>
                    Start Evaluation Run
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
