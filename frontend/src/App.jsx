import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import DemoBanner from './components/DemoBanner'

import Login from './pages/Login'
import Setup from './pages/Setup'
import Home from './pages/Home'
import Company from './pages/Company'
import Chatbots from './pages/Chatbots'
import Pipelines from './pages/Pipelines'
import Skills from './pages/Skills'
import Remote from './pages/Remote'
import Gateway from './pages/Gateway'
import Trust from './pages/Trust'
import Compliance from './pages/Compliance'
import Leads from './pages/Leads'
import Visits from './pages/Visits'
import Reliability from './pages/Reliability'
import Backup from './pages/Backup'
import Universal from './pages/Universal'
import Recipes from './pages/Recipes'
import Rehearsal from './pages/Rehearsal'
import Webhooks from './pages/Webhooks'
import Solutions from './pages/Solutions'
import Verticals from './pages/Verticals'
import AgentTeam from './pages/AgentTeam'
import OrgChart from './pages/OrgChart'
import Tasks from './pages/Tasks'
import Workflows from './pages/Workflows'
import Approvals from './pages/Approvals'
import Inbox from './pages/Inbox'
import Brain from './pages/Brain'
import Graph from './pages/Graph'
import Analytics from './pages/Analytics'
import Marketplace from './pages/Marketplace'
import Billing from './pages/Billing'
import Devices from './pages/Devices'
import Settings from './pages/Settings'
import GuidedSetup from './pages/GuidedSetup'
import Editions from './pages/Editions'
import Dictate from './pages/Dictate'
import Runtime from './pages/Runtime'
import Welcome from './pages/Welcome'
import SystemHealth from './pages/SystemHealth'

import AdminLayout from './admin/AdminLayout'
import AdminHome from './admin/AdminHome'
import AdminTenants from './admin/AdminTenants'
import AdminPlans from './admin/AdminPlans'
import AdminConfig from './admin/AdminConfig'
import AdminHermes from './admin/AdminHermes'
import AdminCatalog from './admin/AdminCatalog'
import AdminEditions from './admin/AdminEditions'
import AdminReleases from './admin/AdminReleases'
import AdminMarketplace from './admin/AdminMarketplace'
import AdminAudit from './admin/AdminAudit'

function UserRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

// Authed but full-screen (no app chrome) — for the first-run install/welcome.
function FullRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function AdminRoute({ children }) {
  const { admin, loading } = useAuth()
  if (loading) return <Loading />
  if (!admin) return <Navigate to="/login" replace />
  return <AdminLayout>{children}</AdminLayout>
}

export default function App() {
  const { user, admin, loading } = useAuth()
  return (
    <>
    <DemoBanner />
    <Routes>
      <Route path="/setup" element={<Setup />} />
      <Route path="/login" element={
        loading ? <Loading /> :
        user ? <Navigate to="/" replace /> :
        admin ? <Navigate to="/admin" replace /> : <Login />
      } />

      <Route path="/" element={<UserRoute><Home /></UserRoute>} />
      <Route path="/guided-setup" element={<UserRoute><GuidedSetup /></UserRoute>} />
      <Route path="/editions" element={<UserRoute><Editions /></UserRoute>} />
      <Route path="/dictate" element={<UserRoute><Dictate /></UserRoute>} />
      <Route path="/company" element={<UserRoute><Company /></UserRoute>} />
      <Route path="/org" element={<UserRoute><OrgChart /></UserRoute>} />
      <Route path="/chatbots" element={<UserRoute><Chatbots /></UserRoute>} />
      <Route path="/agent-team" element={<UserRoute><AgentTeam /></UserRoute>} />
      <Route path="/tasks" element={<UserRoute><Tasks /></UserRoute>} />
      <Route path="/pipelines" element={<UserRoute><Pipelines /></UserRoute>} />
      <Route path="/skills" element={<UserRoute><Skills /></UserRoute>} />
      <Route path="/workflows" element={<UserRoute><Workflows /></UserRoute>} />
      <Route path="/remote" element={<UserRoute><Remote /></UserRoute>} />
      <Route path="/gateway" element={<UserRoute><Gateway /></UserRoute>} />
      <Route path="/compliance" element={<UserRoute><Compliance /></UserRoute>} />
      <Route path="/trust" element={<UserRoute><Trust /></UserRoute>} />
      <Route path="/leads" element={<UserRoute><Leads /></UserRoute>} />
      <Route path="/visits" element={<UserRoute><Visits /></UserRoute>} />
      <Route path="/reliability" element={<UserRoute><Reliability /></UserRoute>} />
      <Route path="/backup" element={<UserRoute><Backup /></UserRoute>} />
      <Route path="/universal" element={<UserRoute><Universal /></UserRoute>} />
      <Route path="/recipes" element={<UserRoute><Recipes /></UserRoute>} />
      <Route path="/rehearsal" element={<UserRoute><Rehearsal /></UserRoute>} />
      <Route path="/webhooks" element={<UserRoute><Webhooks /></UserRoute>} />
      <Route path="/solutions" element={<UserRoute><Solutions /></UserRoute>} />
      <Route path="/verticals" element={<UserRoute><Verticals /></UserRoute>} />
      <Route path="/approvals" element={<UserRoute><Approvals /></UserRoute>} />
      <Route path="/inbox" element={<UserRoute><Inbox /></UserRoute>} />
      <Route path="/brain" element={<UserRoute><Brain /></UserRoute>} />
      <Route path="/graph" element={<UserRoute><Graph /></UserRoute>} />
      <Route path="/analytics" element={<UserRoute><Analytics /></UserRoute>} />
      <Route path="/marketplace" element={<UserRoute><Marketplace /></UserRoute>} />
      <Route path="/billing" element={<UserRoute><Billing /></UserRoute>} />
      <Route path="/devices" element={<UserRoute><Devices /></UserRoute>} />
      <Route path="/settings" element={<UserRoute><Settings /></UserRoute>} />
      <Route path="/runtime" element={<UserRoute><Runtime /></UserRoute>} />
      <Route path="/system-health" element={<UserRoute><SystemHealth /></UserRoute>} />
      <Route path="/welcome" element={<FullRoute><Welcome /></FullRoute>} />

      <Route path="/admin" element={<AdminRoute><AdminHome /></AdminRoute>} />
      <Route path="/admin/tenants" element={<AdminRoute><AdminTenants /></AdminRoute>} />
      <Route path="/admin/plans" element={<AdminRoute><AdminPlans /></AdminRoute>} />
      <Route path="/admin/config" element={<AdminRoute><AdminConfig /></AdminRoute>} />
      <Route path="/admin/hermes" element={<AdminRoute><AdminHermes /></AdminRoute>} />
      <Route path="/admin/catalog" element={<AdminRoute><AdminCatalog /></AdminRoute>} />
      <Route path="/admin/editions" element={<AdminRoute><AdminEditions /></AdminRoute>} />
      <Route path="/admin/releases" element={<AdminRoute><AdminReleases /></AdminRoute>} />
      <Route path="/admin/marketplace" element={<AdminRoute><AdminMarketplace /></AdminRoute>} />
      <Route path="/admin/audit" element={<AdminRoute><AdminAudit /></AdminRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  )
}
