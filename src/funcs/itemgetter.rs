pub enum Index {
    Usize(usize),
    String(String),
}

pub trait ItemGetter<I, O> {
    fn get_item<'a>(&self, item: &'a I) -> Option<&'a O>;
}

pub struct ItemGetter0;
pub struct ItemGetter1<I> {
    item: I,
}

pub struct ItemGetterN<I> {
    items: Vec<I>,
}

impl ItemGetter<serde_json::Value, serde_json::Value> for ItemGetter0 {
    fn get_item<'s>(&self, item: &'s serde_json::Value) -> Option<&'s serde_json::Value> {
        Some(item)
    }
}

impl<I: serde_json::value::Index> ItemGetter<serde_json::Value, serde_json::Value>
    for ItemGetter1<I>
{
    fn get_item<'s>(&self, item: &'s serde_json::Value) -> Option<&'s serde_json::Value> {
        return item.get(&self.item);
    }
}

impl ItemGetter<serde_json::Value, serde_json::Value> for ItemGetterN<Index> {
    fn get_item<'s>(&self, item: &'s serde_json::Value) -> Option<&'s serde_json::Value> {
        let mut ptr = item;
        for i in self.items.iter() {
            ptr = match i {
                Index::Usize(i) => match ptr.get(*i) {
                    None => return None,
                    Some(v) => v,
                },
                Index::String(s) => match ptr.get(s) {
                    None => return None,
                    Some(v) => v,
                },
            }
        }

        Some(ptr)
    }
}

pub fn itemgetter<P: AsRef<str>>(
    item: Option<P>,
) -> Box<dyn ItemGetter<serde_json::Value, serde_json::Value>> {
    match item {
        None => Box::new(ItemGetter0 {}),
        Some(k) => {
            let items = k
                .as_ref()
                .split(".")
                .map(|s| match s.parse::<usize>() {
                    Ok(i) => Index::Usize(i),
                    Err(_) => Index::String(s.to_string()),
                })
                .collect::<Vec<_>>();

            if items.len() == 1 {
                match &items[0] {
                    Index::Usize(i) => Box::new(ItemGetter1 { item: i.to_owned() }),
                    Index::String(s) => Box::new(ItemGetter1 { item: s.to_owned() }),
                }
            } else {
                Box::new(ItemGetterN { items })
            }
        }
    }
}
