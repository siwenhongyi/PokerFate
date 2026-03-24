-- 缓系统接口，使用 DoTween 内核实现

local helper = CS.DoTweenHelper
DT = CS.DG.Tweening

-- 缓动的控制方法
bee.Tween = {
    killAll = function(o)
        if o then
            DT.DOTween.Kill(o.transform)
        -- else
        --     DT.DOTween.KillAll()
        end
    end,
    -- killById = function(id)
    --     helper:KillById(id)
    -- end,
    killByTarget = function(target)
        DT.DOTween.Kill(target)
    end,
    pauseAll = function(o)
        if o then
            DT.DOTween.Pause(o.transform)
        -- else
        --     DT.DOTween.PauseAll()
        end
    end,
    playAll = function(o)
        if o then
            DT.DOTween.Play(o.transform)
        -- else
        --     DT.DOTween.PlayAll()
        end
    end,

    -- 浮点插值回调
    toFloat = function(from, to, dt, cb)
        return helper.TweenToFloat(from, to, dt, cb)
    end,

    -- v3 插值回调
    toVector = function(from, to, dt, cb)
        return helper.TweenToVector3(from, to, dt, cb)
    end,
	toColor = function(from, to, dt, cb)
		return helper.TweenToColor(from, to, dt, cb)
	end,

    sequence = function(seqs)
        local seq = DT.DOTween.Sequence()
        for _, v in ipairs(seqs) do
            if type(v) == "table" then
                seq:Append(v.seq)
            elseif type(v) == "function" then
                helper.TweenOnCallback(seq, v)
            elseif type(v) == "number" then
                seq:AppendInterval(v)
            else
                seq:Append(v.seq)
            end
        end
        return seq
    end,
}

-- 对节点进行简单动画, obj: 执行动画的物体, noLocal: 不是使用局部位置/旋转等
-- 可以使用 move/rotate/scale ，也可以用 to/by 直接设置属性动画
-- repeat(count): 循环
-- delay(dt): 延迟
function bee.tween(obj, noLocal)
    local o = {
        obj = obj,
        seq = nil,  -- 动作队伍
        act = nil,  -- 当前动作
        noLocal = noLocal,
    }

    setmetatable(o, {__index = bee._tweenMeta})

    return o
end

bee._tweenMeta = {
    -- 循环次数，count：-1 为无限循环
    -- 注意，必须在最后调用
    -- CS.DG.Tweening.LoopType Restart Yoyo Incremental
    loop = function(o, count, loopType)
        if o.seq then
            --o.seq:SetLoops(count, loopType or CS.DG.Tweening.LoopType.Restart)
            helper.TweenSeqLoop(o.seq, count, loopType or DT.LoopType.Restart)
        elseif o.act then
            -- o.act:SetLoops(count, loopType or CS.DG.Tweening.LoopType.Restart)
            helper.TweenLoop(o.act, count, loopType or DT.LoopType.Restart)
        end
        return o
    end,

    -- -- 插入队列
    -- sequence = function(o)
    --     o.seq = CS.DG.Tweening.DOTween.Sequence()
    --     return o
    -- end,

    -- 延迟
    delay = function(o, dt)
        if not o.seq then
            o.seq = DT.DOTween.Sequence()
            if o.act then
                o.seq:Append(o.act)
            elseif o.obj and o.obj.transform then
                o:by(dt, {scale = bee.v3(0, 0, 0)})
                return o
            end
        end
        o.seq:AppendInterval(dt)
        return o
    end,

    -- 在队伍前面插入延迟
    predelay = function(o, dt)
        if not o.seq then
            o.seq = DT.DOTween.Sequence()
            if o.act then
                o.seq:Append(o.act)
            end
        end
        o.seq:PrependInterval(dt)
        return o
    end,

    setId = function(o, id)
        if o.seq then
            o.seq:SetId(id)
        elseif o.act then
            o.act:SetId(id)
        end
        return o
    end,

    setTarget = function(o, t)
        if not t then t = o.obj end
        if o.seq then
            o.seq:SetTarget(t)
        elseif o.act then
            o.act:SetTarget(t)
        end
        return o
    end,

    onStart = function(o, func)
        if o.seq then
            --o.seq:OnComplete(func)
            helper.TweenSeqOnStart(o.seq, func)
        elseif o.act then
            --o.act:OnComplete(func)
            helper.TweenOnStart(o.act, func)
        end
        return o
    end,

    -- 结束时回调
    onComplete = function(o, func)
        if o.seq then
            --o.seq:OnComplete(func)
            helper.TweenSeqOnComplete(o.seq, func)
        elseif o.act then
            --o.act:OnComplete(func)
            helper.TweenOnComplete(o.act, func)
        end
        return o
    end,

    -- 每次循环结束时回调
    onStepComplete = function(o, func)
        if o.seq then
            --o.seq:OnComplete(func)
            helper.TweenSeqOnStepComplete(o.seq, func)
        elseif o.act then
            --o.act:OnComplete(func)
            helper.TweenOnStepComplete(o.act, func)
        end
        return o
    end,

    onUpdate = function(o, func)
        if o.seq then
            --o.seq:OnUpdate(func)
            helper.TweenSeqOnUpdate(o.seq, func)
        elseif o.act then
            --o.act:OnUpdate(func)
            helper.TweenOnUpdate(o.act, func)
        end
        return o
    end,

    -- 添加一个回调
    call = function(o, func)
        if not o.seq then
            o.seq = DT.DOTween.Sequence()
            if o.act then
                o.seq:Append(o.act)
            end
        end
        helper.TweenOnCallback(o.seq, func)
        return o
    end,

    kill = function(o)
        if o.seq then
            o.seq:Kill()
        elseif o.act then
            o.act:Kill()
        end
        return o
    end,

    link = function(o, target)
        if o.seq then
            helper.TweenSeqLink(o.seq, o.obj and o.obj.gameObject, DT.LinkBehaviour.KillOnDestroy)
        elseif o.act then
            helper.TweenLink(o.act, o.obj and o.obj.gameObject, DT.LinkBehaviour.KillOnDestroy)
        end
        if target then
            o:setTarget(target)
        end
        return o
    end,

    -- 缓动效果 public enum CS.DG.Tweening.Ease
    -- Unset =0,
    -- Linear =1,
    -- InSine =2,
    -- OutSine =3,
    -- InOutSine =4,
    -- InQuad =5,
    -- OutQuad =6,
    -- InOutQuad =7,
    -- InCubic =8,
    -- OutCubic =9,
    -- InOutCubic =10,
    -- InQuart =11,
    -- OutQuart =12,
    -- InOutQuart =13,
    -- InQuint =14,
    -- OutQuint =15,
    -- InOutQuint =16,
    -- InExpo =17,
    -- OutExpo =18,
    -- InOutExpo =19,
    -- InCirc =20,
    -- OutCirc =21,
    -- InOutCirc =22,
    -- InElastic =23,
    -- OutElastic =24,
    -- InOutElastic =25,
    -- InBack =26,
    -- OutBack =27,
    -- InOutBack =28,
    -- InBounce =29,
    -- OutBounce =30,
    -- InOutBounce =31,
    -- Flash =32,
    -- InFlash =33,
    -- OutFlash =34,
    -- InOutFlash =35,
    -- INTERNAL_Zero =36,
    -- INTERNAL_Custom =37
    ease = function(o, e, isAct)
        if isAct then
            if o.act then
                -- o.act:SetEase(e)
                helper.TweenEase(o.act, e)
            end
            return o
        end
        if o.seq then
            -- o.seq:SetEase(e)
            helper.TweenSeqEase(o.seq, e)
        elseif o.act then
            -- o.act:SetEase(e)
            helper.TweenEase(o.act, e)
        end
        return o
    end,

    -- 沿路径移动 pathType CS.DG.Tweening.PathType Linear CatmullRom CubicBezier 
    path = function(o, ways, dt, pathType)
        if o.noLocal then
            o.act = o.obj.transform:DOPath(ways, dt, pathType or DT.PathType.Linear)
        else
            o.act = o.obj.transform:DOLocalPath(ways, dt, pathType or DT.PathType.Linear)
        end
        return o
    end,

    -- 跟随 toObj 的位置
    follow = function(o, toObj, dt, cb)
        if toObj then
            o:delay(dt)
            o:onUpdate(function()
                if not bee.isNull(o.obj) and not bee.isNull(toObj) then
                    o.obj.transform.position = toObj.transform.position
                end
                if cb then
                    cb()
                end
            end)
        end
        return o
    end,

    -- 移动到 v3, snapping: 是否平滑动作
    moveTo = function(o, v3, dt, snapping)
        return o.to(o, dt, {position = v3}, snapping)
    end,
    moveToX = function(o, x, dt, snapping)
        return o.to(o, dt, {x = x}, snapping)
    end,
    moveToY = function(o, y, dt, snapping)
        return o.to(o, dt, {y = y}, snapping)
    end,
    moveToZ = function(o, z, dt, snapping)
        return o.to(o, dt, {z = z}, snapping)
    end,
    -- 旋转 RotateMode 1Fast(default) 2FastBeyond360 3WorldAxisAdd 4LocalAxisAdd
    rotateTo = function(o, v3, dt, rotateMode)
        return o.to(o, dt, {rotate = v3}, rotateMode)
    end,
    -- 缩放
    scaleTo = function(o, v3, dt)
        return o.to(o, dt, {scale = v3})
    end,
    scaleToX = function(o, x, dt)
        return o.to(o, dt, {scaleX = x})
    end,
    scaleToY = function(o, y, dt)
        return o.to(o, dt, {scaleY = y})
    end,
    scaleToZ = function(o, z, dt)
        return o.to(o, dt, {scaleZ = z})
    end,

    -- 相对移动
    moveBy = function(o, v3, dt, snapping)
        return o.by(o, dt, {position = v3}, snapping)
    end,
    moveByX = function(o, x, dt, snapping)
        return o.by(o, dt, {x = x}, snapping)
    end,
    moveByY = function(o, y, dt, snapping)
        return o.by(o, dt, {y = y}, snapping)
    end,
    moveByZ = function(o, z, dt, snapping)
        return o.by(o, dt, {z = z}, snapping)
    end,
    rotateBy = function(o, v3, dt, rotateMode)
        return o.by(o, dt, {rotate = v3}, rotateMode)
    end,
    scaleBy = function(o, v3, dt)
        return o.by(o, dt, {scale = v3})
    end,
    scaleByX = function(o, x, dt)
        return o.by(o, dt, {scaleX = x})
    end,
    scaleByY = function(o, y, dt)
        return o.by(o, dt, {scaleXY = y})
    end,
    scaleByZ = function(o, z, dt)
        return o.by(o, dt, {scaleZ = z})
    end,

    toFloat = function(o, from, to, dt, cb)
        local act = bee.Tween.toFloat(from, to, dt, cb)
        return o:_appendAct(act)
    end,

    toVector = function(o, from, to, dt, cb)
        local act = bee.Tween.toVector(from, to, dt, cb)
        return o:_appendAct(act)
    end,

    -- 使用属性变化到, attr: 属性k-v表,
    -- position: v3,    transform 位置变化  extra: 是否平滑动作
    -- x, y, z: number, transform 对应位置属性变化  extra: 是否平滑动作
    -- rotate: v3,      transform 旋转  extra: RotateMode 1Fast(default) 2FastBeyond360 3WorldAxisAdd 4LocalAxisAdd
    -- scale: v3,       transform 缩放
    -- scaleX, scaleY, scaleZ: number
    to = function(o, dt, attr, extra)
        local act, obj, flag = nil, o.obj, false
        for k, v in pairs(attr) do
            if "position" == k then
                if o.noLocal then
                    act = obj.transform:DOMove(v, dt, extra and extra.position or false)
                else
                    act = obj.transform:DOLocalMove(v, dt, extra and extra.position or false)
                end
            -- elseif "size" == k then
            --     act = obj.transform:DOSizeDelta(v, dt, extra or false)
			elseif "jump" == k then
				if o.noLocal then
					act = obj.transform:DOJump(v, 1,1,dt, extra and extra.jump or false)
				else
					act = obj.transform:DOLocalJump(v, 100,1,dt, extra and extra.jump or false)
				end
                if not o.seq then
                    o.seq = DT.DOTween.Sequence()
                end
            elseif "x" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveX(v, dt, extra and extra.x or false)
                else
                    act = obj.transform:DOLocalMoveX(v, dt, extra and extra.x or false)
                end
            elseif "y" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveY(v, dt, extra and extra.y or false)
                else
                    act = obj.transform:DOLocalMoveY(v, dt, extra and extra.y or false)
                end
            elseif "z" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveZ(v, dt, extra and extra.z or false)
                else
                    act = obj.transform:DOLocalMoveZ(v, dt, extra and extra.z or false)
                end
            elseif "rotate" == k then
                if o.noLocal then
                    act = obj.transform:DORotate(v, dt, extra and extra.rotate or DT.RotateMode.Fast)
                else
                    act = obj.transform:DOLocalRotate(v, dt, extra and extra.rotate or DT.RotateMode.Fast)
                end
            elseif "scale" == k then
                act = obj.transform:DOScale(v, dt)
            elseif "scaleX" == k then
                act = obj.transform:DOScaleX(v, dt)
            elseif "scaleY" == k then
                act = obj.transform:DOScaleY(v, dt)
            elseif "scaleZ" == k then
                act = obj.transform:DOScaleZ(v, dt)
            elseif "opacity" == k then
                local cmp = obj:GetComponent(extra and extra.opacity or "Image")
                if cmp then
                    local c = cmp.color
                    act = bee.Tween.toFloat(c.a, v, dt, function(v)
                        if not bee.isNull(obj) then
                            cmp.color = CU.Color(c.r, c.g, c.b, v)
                        end
                    end)

                    -- act = cmp:DOFade(v, dt)
                end
            elseif "alpha" == k then
                local cmp = obj:GetComponent(extra and extra.alpha or "CanvasGroup")
                if cmp then
                    act = bee.Tween.toFloat(cmp.alpha, v, dt, function(v)
                        if not bee.isNull(obj) then
                            cmp.alpha = v
                        end
                    end)
                end
            elseif "alphaBetween" == k then
                --指定alpha
                local cmp = obj:GetComponent(extra and extra.alpha or "CanvasGroup")
                if cmp then
                    act = bee.Tween.toFloat(v[1], v[2], dt, function(v)
                        if not bee.isNull(obj) then
                            cmp.alpha = v
                        end
                    end)
                end
            elseif "fillAmount" == k then
                local cmp = obj:GetComponent(extra and extra.Image or "Image")
                if cmp then
                    act = bee.Tween.toFloat(cmp.fillAmount, v, dt, function(v)
                        if not bee.isNull(obj) then
                            cmp.fillAmount = v
                        end
                    end)
                end
            end
            if flag then
                o:_joinAct(act)
            else
                o:_appendAct(act)
            end
            flag = true
        end
        return o
    end,

    -- 相对属性变化
    by = function(o, dt, attr, extra)
        local act, obj, flag = nil, o.obj, false
        for k, v in pairs(attr) do
            if "position" == k then
                if o.noLocal then
                    local old = obj.transform.position;
                    act = obj.transform:DOMove(bee.v3(old.x + v.x, old.y + v.y, old.z + v.z), dt, extra and extra.position or false)
                else
                    local old = obj.transform.localPosition;
                    act = obj.transform:DOLocalMove(bee.v3(old.x + v.x, old.y + v.y, old.z + v.z), dt, extra and extra.position or false)
                end
            -- elseif "size" == k then
            --     local old = obj.transform.sizeDelta
            --     act = obj.transform:DOSizeDelta(bee.v2(old.x + v.x, old.y + v.y), dt, extra or false)
            elseif "x" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveX(v + obj.transform.position.x, dt, extra and extra.x or false)
                else
                    act = obj.transform:DOLocalMoveX(v + obj.transform.localPosition.x, dt, extra and extra.x or false)
                end
            elseif "y" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveY(v + obj.transform.position.y, dt, extra and extra.y or false)
                else
                    act = obj.transform:DOLocalMoveY(v + obj.transform.localPosition.y, dt, extra and extra.y or false)
                end
            elseif "z" == k then
                if o.noLocal then
                    act = obj.transform:DOMoveZ(v + obj.transform.position.z, dt, extra and extra.z or false)
                else
                    act = obj.transform:DOLocalMoveZ(v + obj.transform.localPosition.z, dt, extra and extra.z or false)
                end
            elseif "rotate" == k then
                if o.noLocal then
                    local old = obj.transform.eulerAngles
                    act = obj.transform:DORotate(bee.v3(old.x + v.x, old.y + v.y, old.z + v.z), dt, extra and extra.rotate or DT.RotateMode.Fast)
                else
                    local old = obj.transform.localEulerAngles
                    act = obj.transform:DOLocalRotate(bee.v3(old.x + v.x, old.y + v.y, old.z + v.z), dt, extra and extra.rotate or DT.RotateMode.Fast)
                end
            elseif "scale" == k then
                local old = obj.transform.localScale;
                act = obj.transform:DOScale(bee.v3(old.x + v.x, old.y + v.y, old.z + v.z), dt)
            elseif "scaleX" == k then
                act = obj.transform:DOScaleX(v + obj.transform.localScale.x, dt)
            elseif "scaleY" == k then
                act = obj.transform:DOScaleY(v + obj.transform.localScale.y, dt)
            elseif "scaleZ" == k then
                act = obj.transform:DOScaleZ(v + obj.transform.localScale.z, dt)
            elseif "opacity" == k then
                local cmp = obj:GetComponent(extra and extra.opacity or "Image")
                if cmp then
                    local c = cmp.color
                    act = bee.Tween.toFloat(c.a, c.a + v, dt, function(v)
                        if not bee.isNull(obj) then
                            cmp.color = CU.Color(c.r, c.g, c.b, v)
                        end
                    end)
                end
            end
            if flag then
                o:_joinAct(act)
            else
                o:_appendAct(act)
            end
            flag = true
        end
        return o
    end,

    _appendAct = function(o, act)
        if act and o.act then
            if not o.seq then
                o.seq = DT.DOTween.Sequence()
                o.seq:Append(o.act)
            end
        end
        if o.seq then
            o.seq:Append(act)
        end
        o.act = act
        return o
    end,

     _joinAct = function(o, act)
        if not o.seq then
            o.seq = DT.DOTween.Sequence()
            if o.act then
                o.seq:Append(o.act)
            end
        end
        o.seq:Join(act)
     end,
