-- google play mgr
local P = {
    _isLogin = nil, -- 是否已经登录
    _loginCb = nil,
    _checkCb = nil,

    _playerId = nil,    -- 玩家 id
    _playerIdCb = nil,

    _token = nil,   -- token
    _tokenCb = nil,
}
GoogleMgr = P

------------ java 响应 开始 -------------
function onGooglePlayIsLogin(isLogin)
    P._isLogin = isLogin
    print("onGooglePlayIsLogin", isLogin, P._loginCb)
    if P._loginCb then
        P._loginCb(isLogin)
        P._loginCb = nil
    end
    if P._checkCb then
        P._checkCb(isLogin)
        P._checkCb = nil
    end
end

function onGooglePlayPlayerId(playerId)
    P._playerId = playerId
    if P._playerIdCb then
        P._playerIdCb(playerId)
        P._playerIdCb = nil
    end
end

function onGooglePlayToken(token)
    P._token = token
    if P._tokenCb then
        P._tokenCb(token)
        P._tokenCb = nil
    end
end

------------ java 响应 结束 -------------

function P:login(cb)
    self._loginCb = cb
    CS.GoogleMgr.login()
end

function P:checkLogin(cb)
    if bee.isPc then
        cb(true)
    elseif nil ~= self._isLogin then
        cb(self._isLogin)
    else
        self._checkCb = cb
        CS.GoogleMgr.checkLogin()
    end
end

function P:getPlayerId(cb)
    if self._playerId then
        cb(self._playerId)
    else
        self._playerIdCb = cb
        CS.GoogleMgr.getPlayerId()
    end
end

function P:loginServer(cb)
    if self._token then
        cb(self._token)
    else
        self._tokenCb = cb
        CS.GoogleMgr.loginServer()
    end
end

function P:unlockAchievement(id)
    CS.GoogleMgr.unlockAchievement(id)
end

function P:incrementAchievement(id, inc)
    CS.GoogleMgr.incrementAchievement(id, inc)
end

function P:showAchievements()
    CS.GoogleMgr.showAchievements()
end

function P:getClientId()
    return CS.GoogleMgr.getClientId()
