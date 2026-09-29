import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'SPAD.neXt Documentation',
  tagline: 'Simulation Panel Advanced Drivers: neXt Generation',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  url: 'https://docs.spadnext.com',
  baseUrl: '/',

  organizationName: 'SPAD-neXt',
  projectName: 'spad-docs',

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl: 'https://github.com/SPAD-neXt/spad-docs/tree/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'SPAD.neXt Documentation',
      logo: {
        alt: 'SPAD.neXt Logo',
        src: 'img/logo.png',
      },
      items: [
        {
          href: 'https://github.com/SPAD-neXt/spad-docs',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      links: [],
      copyright: `Copyright © ${new Date().getFullYear()} SPAD.neXt. Built with <a href="https://github.com/facebook/docusaurus" target="_blank" rel="noopener noreferrer">Docusaurus</a>.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
