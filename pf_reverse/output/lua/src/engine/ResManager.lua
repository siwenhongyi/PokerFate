local res_loader = {}

SpriteManager = CS.SpriteManager.Instance
ResManager = CS.ResManager.Instance

local function _getLoader(type_, funcName)
    local loaderFunc = xlua.get_generic_method(CS.ResManager, funcName)
    local fn = loaderFunc(typeof(type_))
    return fn
end

-- 预加载资源 type_: CS.UnityEngine.GameObject 加载类型, cb(path, bool)
bee.preloadAsyn = function(type_, path, cb)
    local fn = _getLoader(type_, "PreloadAsyn")
    fn(ResManager, path, cb)
end

-- 同步加载资源
bee.addressableSynLoad = function(type_, path)
    local fn = _getLoader(type_, "AddressableSynLoad")
    return realFunc(ResManager, path)
