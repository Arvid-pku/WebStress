import { useEffect } from "react";

import { useRedditLayout } from "../context";
import type { RedditSettings } from "../types";

export function SettingsPage() {
  const { settings, notify, refreshSettings, updateSettings } = useRedditLayout();

  useEffect(() => {
    if (settings) {
      return;
    }
    void refreshSettings().catch(() => {
      notify("Failed to load settings");
    });
  }, [notify, refreshSettings, settings]);

  const handleUpdate = async (updates: Partial<RedditSettings>) => {
    try {
      await updateSettings(updates);
      notify("Settings updated");
    } catch {
      notify("Failed to update settings");
    }
  };

  if (!settings) return <div className="settings-page__loading">Loading settings...</div>;

  return (
    <div className="settings-page">
      <h1 className="settings-page__title">User Settings</h1>

      <section className="settings-section" aria-label="Feed settings">
        <h2 className="settings-section__title">Feed</h2>
        <div className="settings-field">
          <label htmlFor="feed-sort">Default feed sort</label>
          <select id="feed-sort" value={settings.default_feed_sort} onChange={(e) => handleUpdate({ default_feed_sort: e.target.value })}>
            <option value="hot">Hot</option>
            <option value="new">New</option>
            <option value="top">Top</option>
            <option value="rising">Rising</option>
          </select>
        </div>
        <div className="settings-field">
          <label htmlFor="comment-sort">Default comment sort</label>
          <select id="comment-sort" value={settings.default_comment_sort} onChange={(e) => handleUpdate({ default_comment_sort: e.target.value })}>
            <option value="best">Best</option>
            <option value="top">Top</option>
            <option value="new">New</option>
            <option value="controversial">Controversial</option>
            <option value="old">Old</option>
          </select>
        </div>
      </section>

      <section className="settings-section" aria-label="Display settings">
        <h2 className="settings-section__title">Display</h2>
        <div className="settings-field settings-field--toggle">
          <label htmlFor="theme-select">Theme</label>
          <select id="theme-select" value={settings.theme} onChange={(e) => handleUpdate({ theme: e.target.value })}>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Compact view" checked={settings.compact_view} onChange={(e) => handleUpdate({ compact_view: e.target.checked })} />
            Compact view
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Open links in new tab" checked={settings.open_links_in_new_tab} onChange={(e) => handleUpdate({ open_links_in_new_tab: e.target.checked })} />
            Open links in new tab
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Auto-play media" checked={settings.auto_play_media} onChange={(e) => handleUpdate({ auto_play_media: e.target.checked })} />
            Auto-play media
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Reduce animations" checked={settings.reduce_animations} onChange={(e) => handleUpdate({ reduce_animations: e.target.checked })} />
            Reduce animations
          </label>
        </div>
      </section>

      <section className="settings-section" aria-label="Content settings">
        <h2 className="settings-section__title">Content</h2>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Show NSFW content" checked={settings.show_nsfw} onChange={(e) => handleUpdate({ show_nsfw: e.target.checked })} />
            Show NSFW content
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Blur NSFW images" checked={settings.blur_nsfw} onChange={(e) => handleUpdate({ blur_nsfw: e.target.checked })} />
            Blur NSFW images
          </label>
        </div>
        <div className="settings-field">
          <label htmlFor="language-select">Language</label>
          <select id="language-select" value={settings.language} onChange={(e) => handleUpdate({ language: e.target.value })}>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="ja">Japanese</option>
            <option value="zh">Chinese</option>
          </select>
        </div>
        <div className="settings-field">
          <label htmlFor="country-select">Country</label>
          <select id="country-select" value={settings.country} onChange={(e) => handleUpdate({ country: e.target.value })}>
            <option value="US">United States</option>
            <option value="GB">United Kingdom</option>
            <option value="CA">Canada</option>
            <option value="AU">Australia</option>
            <option value="DE">Germany</option>
            <option value="FR">France</option>
            <option value="JP">Japan</option>
          </select>
        </div>
      </section>

      <section className="settings-section" aria-label="Notification settings">
        <h2 className="settings-section__title">Notifications</h2>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Email on comment replies" checked={settings.email_comment_reply} onChange={(e) => handleUpdate({ email_comment_reply: e.target.checked })} />
            Email on comment replies
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Email on post replies" checked={settings.email_post_reply} onChange={(e) => handleUpdate({ email_post_reply: e.target.checked })} />
            Email on post replies
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Email on mentions" checked={settings.email_mentions} onChange={(e) => handleUpdate({ email_mentions: e.target.checked })} />
            Email on mentions
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Email on private messages" checked={settings.email_messages} onChange={(e) => handleUpdate({ email_messages: e.target.checked })} />
            Email on private messages
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Email digest" checked={settings.email_digest} onChange={(e) => handleUpdate({ email_digest: e.target.checked })} />
            Email digest
          </label>
        </div>
      </section>

      <section className="settings-section" aria-label="Privacy settings">
        <h2 className="settings-section__title">Privacy</h2>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Show online status" checked={settings.show_online_status} onChange={(e) => handleUpdate({ show_online_status: e.target.checked })} />
            Show online status
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Allow followers" checked={settings.allow_followers} onChange={(e) => handleUpdate({ allow_followers: e.target.checked })} />
            Allow followers
          </label>
        </div>
        <div className="settings-field settings-field--toggle">
          <label>
            <input type="checkbox" aria-label="Show active communities" checked={settings.show_active_communities} onChange={(e) => handleUpdate({ show_active_communities: e.target.checked })} />
            Show active communities in profile
          </label>
        </div>
      </section>
    </div>
  );
}
