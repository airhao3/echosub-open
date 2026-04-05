import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
  styled,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Folder as ProjectsIcon,
  Upload as UploadIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';

const drawerWidth = 260;

const Sidebar = styled('div')(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  backgroundColor: theme.palette.mode === 'dark' ? '#1C1C1E' : '#FBFBFD',
  color: theme.palette.text.primary,
  padding: theme.spacing(2, 0),
  borderRight: theme.palette.mode === 'dark'
    ? '1px solid rgba(255, 255, 255, 0.06)'
    : '1px solid rgba(0, 0, 0, 0.06)',
}));

const SidebarHeader = styled('div')(({ theme }) => ({
  padding: '0 16px 16px',
  marginBottom: 8,
  borderBottom: theme.palette.mode === 'dark'
    ? '1px solid rgba(255, 255, 255, 0.06)'
    : '1px solid rgba(0, 0, 0, 0.06)',
}));

const SidebarSection = styled('div')({
  padding: '8px 0',
});

const SectionTitle = styled(Typography)(({ theme }) => ({
  padding: '8px 24px',
  color: theme.palette.text.secondary,
  fontSize: '0.7rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
}));

const StyledListItem = styled(ListItem)(({ theme }) => ({
  padding: '2px 12px',
  '& .MuiListItemButton-root': {
    borderRadius: 10,
    padding: '8px 12px',
    '&:hover': {
      backgroundColor: theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.05)'
        : 'rgba(0, 0, 0, 0.03)',
    },
    '&.Mui-selected': {
      backgroundColor: theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.08)'
        : 'rgba(0, 0, 0, 0.05)',
      '&:hover': {
        backgroundColor: theme.palette.mode === 'dark'
          ? 'rgba(255, 255, 255, 0.1)'
          : 'rgba(0, 0, 0, 0.07)',
      },
    },
  },
  '& .MuiListItemIcon-root': {
    minWidth: 36,
    color: theme.palette.text.secondary,
  },
  '& .MuiListItemText-primary': {
    fontSize: '0.875rem',
    fontWeight: 500,
    color: theme.palette.text.primary,
  },
}));

const MainContent = styled('main')(({ theme }) => ({
  flexGrow: 1,
  backgroundColor: theme.palette.background.default,
  [theme.breakpoints.down('md')]: { marginLeft: 0 },
}));

const MainLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();

  const menuItems = [
    { text: '工作台', icon: <DashboardIcon />, path: '/dashboard' },
    { text: '项目列表', icon: <ProjectsIcon />, path: '/dashboard/projects' },
    { text: '新建任务', icon: <UploadIcon />, path: '/dashboard/upload' },
    { text: '系统设置', icon: <TuneIcon />, path: '/dashboard/settings' },
  ];

  const drawer = (
    <Sidebar>
      <SidebarHeader>
        <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 600, letterSpacing: '-0.02em' }}>
            EchoSub
          </Typography>
        </Link>
      </SidebarHeader>
      <SidebarSection>
        <SectionTitle>导航菜单</SectionTitle>
        <List>
          {menuItems.map((item) => (
            <StyledListItem key={item.text} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={pathname === item.path || (item.path !== '/dashboard' && pathname.startsWith(item.path))}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </StyledListItem>
          ))}
        </List>
      </SidebarSection>
    </Sidebar>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* Mobile-only top bar */}
      <AppBar
        position="fixed"
        sx={{
          display: { xs: 'block', md: 'none' },
          width: '100%',
          backgroundColor: theme.palette.background.paper,
          color: 'text.primary',
          boxShadow: 'none',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
        elevation={0}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setMobileOpen(!mobileOpen)}
            sx={{ mr: 2, display: { md: 'none' }, color: 'text.primary' }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
            {menuItems.find(item =>
              item.path === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(item.path)
            )?.text || 'EchoSub'}
          </Typography>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}>
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            sx={{
              display: { xs: 'block', md: 'none' },
              '& .MuiDrawer-paper': { width: drawerWidth },
            }}
          >
            {drawer}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: 'none', md: 'block' },
              '& .MuiDrawer-paper': { width: drawerWidth, borderRight: 'none' },
            }}
            open
          >
            {drawer}
          </Drawer>
        )}
      </Box>

      <MainContent sx={{ height: '100vh', overflow: 'hidden' }}>
        <Box sx={{ height: '100%', overflow: 'auto' }}>
          <Outlet />
        </Box>
      </MainContent>
    </Box>
  );
};

export default MainLayout;
