local P = class("ShareModel", BaseModel)

function P:ctor(logic)
    self.saveData = {}

    P.super.ctor(self)
end

function P:initShareList()
    self._sharePageList = {}
    Net:post("game/getSharePage", nil, function(data)
        if data.code ~= 0 then
            return
        end

        self._sharePageList = data.list
    end)
end

-- 分享
function P:requestSharePage(id)
    Net:post("game/sharePage", {id = id}, function(data)
        if data.code ~= 0 then
            return
        end

        if data.item_list then
            ShopModel:showRewardView(data.item_list)
        end

        if not self._sharePageList then
            self._sharePageList = {}
        end
        table.insert(self._sharePageList, id)

        bee.emit("evt_updateSharedPage")
    end)
end

-- 是否已分享
function P:getPageIsShared(id)
    if not self._sharePageList then
        return false
    end

    for k, v in pairs(self._sharePageList) do
        if v == id then
            return true
        end
    end
    return false
end

-- 分享通用设置
function P:setShareCont(rewardCont, Icon, CountText, id)
    if bee.isPc then
        rewardCont:SetActive(false)
        return
    end

    if self:getPageIsShared(id) then
        rewardCont:SetActive(false)
    elseif tpl_share_config[id] and tpl_share_config[id].reward then
        rewardCont:SetActive(true)
        if Icon then
            bee.setIconInAtlas(Icon, tpl_props[tpl_share_config[id].reward[1]].icon)
        end
        if CountText then
            bee.setText(CountText, "x" .. tpl_share_config[id].reward[2])
        end
    else
        rewardCont:SetActive(false)
    end
end

