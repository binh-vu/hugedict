use rocksdb::IngestExternalFileOptions;
use rocksdb::{Options, DB, SstFileWriter};
use tempfile::tempdir;
use anyhow::Result;


#[test]
fn test_get_set() -> Result<()> {
    let dir = tempdir()?;
    let dbpath = dir.path();

    let mut opts = Options::default();
    opts.create_if_missing(true);

    {
        let db = DB::open(&opts, dbpath)?;
        db.put("P276", "location")?;
    }

    {
        let db = DB::open(&opts, dbpath)?;
        assert_eq!(
            "location",
            String::from_utf8(db.get("P276")?.unwrap_or(vec![]))?
        );
    }
    Ok(())
}

#[test]
fn test_ingest_sst() -> Result<()> {
    let dir = tempdir()?;
    let dbpath = dir.path().join("database.db");

    let mut opts = Options::default();
    opts.create_if_missing(true);

    // test ingest external sst
    {
        let mut writer = SstFileWriter::create(&opts);
        writer.open(&dir.path().join("file.sst"))?;
        writer.put("P276", "location")?;
        writer.finish()?;
        
        let mut ingest_opts = IngestExternalFileOptions::default();
        ingest_opts.set_move_files(true);

        let db = DB::open(&opts, &dbpath)?;
        db.ingest_external_file_opts(&ingest_opts, vec![&dir.path().join("file.sst")])?;
    }

    {
        let db = DB::open(&opts, dbpath)?;
        assert_eq!(
            "location",
            String::from_utf8(db.get("P276")?.unwrap_or(vec![]))?
        );
    }

    Ok(())
}