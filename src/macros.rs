macro_rules! def_pyfunction {
    ($module:ident, $modulepath:literal, $($args:ident),+) => {{
        let func = wrap_pyfunction!($($args),+, $module)?;
        func.setattr("__module__", $modulepath)?;
        $module.add_function(func)?;
    }};
}

macro_rules! call_method {
    ($self:ident.$fn:ident ( $($before:expr),+ ; $middle:expr ; $($after:expr),+ ) ) => {
        $self.$fn($($before),+, $middle, $($after)+)
    };
    ($self:ident.$fn:ident ( ; $middle:expr ; $($after:expr),+ )) => {
        $self.$fn($middle, $($after)+)
    };
    ($self:ident.$fn:ident ( $($before:expr),+ ; $middle:expr ; ) ) => {
        $self.$fn($($before),+, $middle)
    };
    ($self:ident.$fn:ident ( ; $middle:expr ; ) ) => {
        $self.$fn($middle)
    };
}

pub(crate) use call_method;
pub(crate) use def_pyfunction;
