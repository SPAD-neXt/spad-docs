import React, {type JSX} from 'react';
import styles from './styles.module.css';

interface VideoLinkProps {
  id: string;
  title: string;
}

export default function VideoLink({id, title}: VideoLinkProps): JSX.Element {
  const url = `https://youtu.be/${id}`;
  const thumbnail = `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={styles.videoLink}>
      <span className={styles.thumbnailWrapper}>
        <img
          src={thumbnail}
          alt={title}
          loading="lazy"
          className={styles.thumbnail}
        />
        <span className={styles.playButton} aria-hidden="true" />
      </span>
      <span className={styles.title}>{title}</span>
    </a>
  );
}
