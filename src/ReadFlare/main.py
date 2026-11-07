import engine
import database
import time
import requests
import json
import diff
import settings
import config
import watchlist
import notify
import traceback
import change_record
import report

#handles network and file errors
def run_check(last_timestamp):
    try:
        data = engine.fetch_releases()
        # data = engine.load_sample_data()
    except (requests.exceptions.RequestException, OSError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}")
        return engine.TrackerStatus.FETCH_ERROR, last_timestamp, {}
    
    return engine.checkChange(data, last_timestamp)

def newUpdate(new_timestamp):

    database.update_last_timestamp(new_timestamp=new_timestamp)
    print(f"new timestamp: {new_timestamp}")

def process_update(new_timestamp, release):
    release_name = release.get("name") or "currentRelease"
    release_title = release.get("description") or release_name
    release_date = release.get("releaseStartDate")                    

    if config.LAST_EDITION_PATH.exists():
        include_ch99 = settings.get_setting("track_ch99_links")

        changes, old_edition, new_edition = diff.get_diff(
            last_edition_path=config.LAST_EDITION_PATH,
            latest_edition_path=config.LATEST_EDITION_PATH,
            include_ch99=include_ch99,
        )

        record_rows = change_record.get_change_record(release_name or "currentRelease")
        changes = change_record.reconcile(record_rows, changes, include_ch99=include_ch99)

        # changes the change record didn't list: use the release's start date
        if release_date:
            fallback_date = change_record.to_iso_date(release_date)
            for c in changes:
                if not c.get("effective_date"):
                    c["effective_date"] = fallback_date
                    c["source"] = c.get("source") or "Not listed in change record"
        
        split = watchlist.split_by_watchlist(changes, database.get_watchlist_codes())
        run_id = database.store_run(new_timestamp,split=split, release_name=release_name)

        tag = release_name.replace(" ", "_")
        html_report = csv_report = None

        # save a local copy of the report every run, even when no email is sent
        try:
            html_report = report.build_report_html(run_id)
            csv_report = report.build_report_csv(run_id)
            config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            html_path = config.REPORTS_DIR / f"hts_changes_{tag}_run{run_id}.html"
            csv_path = config.REPORTS_DIR / f"hts_changes_{tag}_run{run_id}.csv"
            html_path.write_text(html_report, encoding="utf-8")
            csv_path.write_text(csv_report, encoding="utf-8")
            print(f"Report saved: {html_path}")
        except Exception as e:
            print(f"Could not save local report: {e}")

        try:
            summary = report.build_email_summary(run_id)

            if summary is None:
                database.set_alert_status(run_id=run_id, status="nothing_to_send")
                print("Nothing to send")
            else:
                subject, body = summary
                print(subject)
                print(body)

                # reuse the reports built above; rebuild only if that step failed
                if html_report is None:
                    html_report = report.build_report_html(run_id)
                if csv_report is None:
                    csv_report = report.build_report_csv(run_id)

                attachments = [
                    (f"hts_changes_{tag}.html", html_report, "html"),
                    (f"hts_changes_{tag}.csv", csv_report, "csv"),
                ]

                if notify.send_alert(subject=subject, body=body, attachments=attachments):
                    database.set_alert_status(run_id, "sent")
                    print("Email sent")
                else:
                    database.set_alert_status(run_id, "email_disabled")
                    print("Email Disabled")

        except Exception as e:
            print(f"Alert failed: {e}")
            database.set_alert_status(run_id=run_id, status="failed")
    else:
        print("No previous edition, saving this one as the baseline.")

    # promote latest -> last, so the next update diffs against this one
    config.LATEST_EDITION_PATH.replace(config.LAST_EDITION_PATH)
    newUpdate(new_timestamp=new_timestamp)


if __name__ == "__main__":
    #init db if not exists
    database.init_db()
    if database.watchlist_is_empty():
        database.watchlist_from_json(config.SEED_WATCHLIST_PATH)

    #get config and setting values
    fallback_timestamp = settings.get_setting("fallback_timestamp")
    
    #check if last_timestamp exists in disk
    last_timestamp = database.get_last_timestamp(fallback_timestamp)

    try:
        while True:
            try:
                result, new_timestamp, release = run_check(last_timestamp)
                
                print(f"Loop Check Result: {result.value}")
                
                if(result == engine.TrackerStatus.NEW_UPDATE):

                    #download the new edition and creates latestEdition.json
                    if(engine.fetch_latest_edition()):
                        process_update(new_timestamp=new_timestamp, release=release)                
                        last_timestamp = new_timestamp
                    else:
                        #failed fetch
                        print("Failed to fetch latest Edition, will retry next check.")
                
            except Exception as e:
                print(f"Check failed: {e}")
                traceback.print_exc()
            
            #sleep till next check
            time.sleep(settings.get_setting("check_interval_minutes") * 60)
    
    except KeyboardInterrupt:
        print("\nShutting down.")

