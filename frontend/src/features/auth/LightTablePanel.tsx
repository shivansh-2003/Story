import styles from "./LightTablePanel.module.css";

export function LightTablePanel() {
  return (
    <div className={styles.panel}>
      <div className={styles.sheet}>
        <p className={styles.line}>"She had never seen the lighthouse lit."</p>
        <p className={styles.attribution}>— chapter four, draft</p>
      </div>
    </div>
  );
}
